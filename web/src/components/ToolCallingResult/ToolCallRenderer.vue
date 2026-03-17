<template>
  <WebSearchTool v-if="isWebSearchResult" :tool-call="toolCall" />

  <ChartTool v-else-if="isChartResult" :tool-call="toolCall" />

  <ListKbsTool v-else-if="toolName === 'list_kbs'" :tool-call="toolCall" />

  <GetMindmapTool v-else-if="toolName === 'get_mindmap'" :tool-call="toolCall" />

  <QueryKbTool v-else-if="toolName === 'query_kb'" :tool-call="toolCall" />

  <TodoListTool v-else-if="toolName === 'write_todos'" :tool-call="toolCall" />

  <CalculatorTool v-else-if="isCalculatorResult" :tool-call="toolCall" />

  <ImageTool v-else-if="isImageResult" :tool-call="toolCall" />

  <TaskTool v-else-if="isTaskResult" :tool-call="toolCall" />

  <WriteFileTool v-else-if="toolName === 'write_file'" :tool-call="toolCall" />

  <ReadFileTool v-else-if="toolName === 'read_file'" :tool-call="toolCall" />

  <ListDirectoryTool
    v-else-if="toolName === 'list_directory' || toolName === 'ls'"
    :tool-call="toolCall"
  />

  <SearchFileContentTool v-else-if="toolName === 'search_file_content'" :tool-call="toolCall" />

  <GlobTool v-else-if="toolName === 'glob'" :tool-call="toolCall" />

  <EditFileTool
    v-else-if="toolName === 'edit_file' || toolName === 'replace'"
    :tool-call="toolCall"
  />

  <MysqlQueryTool v-else-if="toolName === 'mysql_query'" :tool-call="toolCall" />

  <MysqlDescribeTableTool v-else-if="toolName === 'mysql_describe_table'" :tool-call="toolCall" />

  <MysqlListTablesTool v-else-if="toolName === 'mysql_list_tables'" :tool-call="toolCall" />

  <AskUserQuestionTool v-else-if="toolName === 'ask_user_question'" :tool-call="toolCall" />

  <BaseToolCall v-else :tool-call="toolCall" />
</template>

<script setup>
import { computed } from 'vue'
import BaseToolCall from './BaseToolCall.vue'

import WebSearchTool from './tools/WebSearchTool.vue'
import ListKbsTool from './tools/ListKbsTool.vue'
import GetMindmapTool from './tools/GetMindmapTool.vue'
import QueryKbTool from './tools/QueryKbTool.vue'
import ChartTool from './tools/ChartTool.vue'
import CalculatorTool from './tools/CalculatorTool.vue'
import TodoListTool from './tools/TodoListTool.vue'
import ImageTool from './tools/ImageTool.vue'
import TaskTool from './tools/TaskTool.vue'
import WriteFileTool from './tools/WriteFileTool.vue'
import ReadFileTool from './tools/ReadFileTool.vue'
import ListDirectoryTool from './tools/ListDirectoryTool.vue'
import SearchFileContentTool from './tools/SearchFileContentTool.vue'
import GlobTool from './tools/GlobTool.vue'
import EditFileTool from './tools/EditFileTool.vue'
import MysqlQueryTool from './tools/MysqlQueryTool.vue'
import MysqlDescribeTableTool from './tools/MysqlDescribeTableTool.vue'
import MysqlListTablesTool from './tools/MysqlListTablesTool.vue'
import AskUserQuestionTool from './tools/AskUserQuestionTool.vue'

const props = defineProps({
  toolCall: {
    type: Object,
    required: true
  }
})

const toolName = computed(() => props.toolCall.name || props.toolCall.function?.name || '')

const parseData = (content) => {
  if (typeof content === 'string') {
    try {
      return JSON.parse(content)
    } catch (error) {
      return content
    }
  }
  return content
}

const isWebSearchResult = computed(() => {
  const name = toolName.value.toLowerCase()
  return name.includes('tavily_search')
})

const isTaskResult = computed(() => {
  let args = props.toolCall.args || props.toolCall.function?.arguments
  if (typeof args === 'string') {
    try {
      args = JSON.parse(args)
    } catch {
      return false
    }
  }
  return args && typeof args === 'object' && 'subagent_type' in args
})

const isCalculatorResult = computed(() => {
  const name = toolName.value.toLowerCase()
  return name.includes('calculator') || name.includes('calc') || name.includes('math')
})

const isChartResult = computed(() => {
  const name = toolName.value.toLowerCase()
  if (!name.includes('chart')) return false
  const data = parseData(props.toolCall.tool_call_result?.content)
  return Array.isArray(data) && data.length > 0 && data[0].type === 'text'
})

const isImageResult = computed(() => {
  const name = toolName.value.toLowerCase()
  if (!name.includes('text_to_img')) return false
  const data = parseData(props.toolCall.tool_call_result?.content)
  return data && typeof data === 'string' && data.startsWith('http')
})
</script>

<style lang="less" scoped></style>
