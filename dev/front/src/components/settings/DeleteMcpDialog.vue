<script setup lang="ts">
// 删除 MCP 服务器确认弹窗(UI-DESIGN §4.2):点明"下次会话装配不再可用"。
import ConfirmDialog from './ConfirmDialog.vue'
import { deleteMessage } from './mcpModel'

defineProps<{ open: boolean; name: string; busy?: boolean }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <ConfirmDialog
    :open="open"
    data-testid="mcp-delete-confirm"
    title="删除 MCP 服务器"
    :message="deleteMessage(name)"
    confirm-text="删除"
    variant="danger"
    :busy="busy"
    @confirm="emit('confirm')"
    @cancel="emit('cancel')"
  />
</template>