/**
 * Vitest(node 环境,无 localStorage)用的内存 Storage 假件。
 * 只在测试里 stubGlobal 使用,不参与生产构建。
 */
export function createFakeStorage(): Storage {
  const map = new Map<string, string>()
  return {
    get length(): number {
      return map.size
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => void map.delete(key),
    setItem: (key: string, value: string) => void map.set(key, value),
  }
}