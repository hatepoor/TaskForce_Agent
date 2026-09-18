/**
 * localStorage JSON 封装:版本信封 + 全链路容错。
 *
 * 禁用存储 / 隐私模式 / 脏数据 / 配额超限一律降级(回退初值或静默丢弃),
 * 绝不把异常抛给业务层——本地持久化失败最多丢标题,不该让工作台打不开。
 *
 * 写入链路:state 是浅响应式视图,修改一律走 write() / update() 并立刻落盘;
 * 直接改 state.value 的嵌套字段既不会触发更新也不会落盘。
 */
import { shallowRef, type ShallowRef } from 'vue'

/** 会话元数据:{ [threadId]: { title, createdAt, lastActiveAt } }(模块 06)。 */
export const THREAD_META_KEY = 'tf.threads'
/** 当前会话 id(裸字符串,不走版本信封)。 */
export const CURRENT_THREAD_KEY = 'tf.currentThreadId'

const ENVELOPE_VERSION = 1

interface Envelope<T> {
  v: number
  data: T
}

export interface LocalStore<T extends object> {
  state: ShallowRef<T>
  /** 从盘上重读(外部改过 localStorage 时用);读失败回退初值 */
  read(): T
  /** 整体替换并落盘 */
  write(value: T): void
  /** 读-改-写:mutate 收到的是浅拷贝,直接改它 */
  update(mutate: (draft: T) => void): T
  /** 重置为初值并移除键 */
  clear(): void
}

/** 隐私模式下访问 localStorage 本身就可能抛异常,统一收口。 */
function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

function drop(key: string): void {
  const ls = storage()
  if (ls === null) return
  try {
    ls.removeItem(key)
  } catch {
    /* 忽略:清不掉也不影响本次会话 */
  }
}

function isEnvelope<T>(value: unknown, version: number): value is Envelope<T> {
  if (typeof value !== 'object' || value === null) return false
  const env = value as { v?: unknown; data?: unknown }
  return env.v === version && typeof env.data === 'object' && env.data !== null
}

function load<T extends object>(key: string, initial: T, version: number): T {
  const ls = storage()
  if (ls === null) return { ...initial }

  let raw: string | null = null
  try {
    raw = ls.getItem(key)
  } catch {
    return { ...initial }
  }
  if (raw === null) return { ...initial }

  try {
    const parsed: unknown = JSON.parse(raw)
    if (isEnvelope<T>(parsed, version)) return parsed.data
    console.warn(`[localStore] ${key} 版本或结构不符,已重置`)
  } catch {
    console.warn(`[localStore] ${key} 不是合法 JSON,已重置`)
  }
  drop(key)
  return { ...initial }
}

function save<T>(key: string, value: T, version: number): void {
  const ls = storage()
  if (ls === null) return
  try {
    const env: Envelope<T> = { v: version, data: value }
    ls.setItem(key, JSON.stringify(env))
  } catch (e) {
    console.warn(`[localStore] ${key} 写入失败(配额或隐私模式)`, e)
  }
}

export function useLocalStore<T extends object>(
  key: string,
  initial: T,
  version: number = ENVELOPE_VERSION,
): LocalStore<T> {
  const state = shallowRef(load(key, initial, version)) as ShallowRef<T>

  function read(): T {
    state.value = load(key, initial, version)
    return state.value
  }

  function write(value: T): void {
    state.value = value
    save(key, value, version)
  }

  function update(mutate: (draft: T) => void): T {
    const draft: T = { ...state.value }
    mutate(draft)
    write(draft)
    return draft
  }

  function clear(): void {
    state.value = { ...initial }
    drop(key)
  }

  return { state, read, write, update, clear }
}

/** 当前会话 id:读失败回 null,由 store 决定回落到新生成的 id。 */
export function readCurrentThreadId(): string | null {
  const ls = storage()
  if (ls === null) return null
  try {
    const id = ls.getItem(CURRENT_THREAD_KEY)
    return id !== null && id !== '' ? id : null
  } catch {
    return null
  }
}

export function writeCurrentThreadId(threadId: string): void {
  const ls = storage()
  if (ls === null) return
  try {
    ls.setItem(CURRENT_THREAD_KEY, threadId)
  } catch {
    /* 不持久化不影响本次会话 */
  }
}