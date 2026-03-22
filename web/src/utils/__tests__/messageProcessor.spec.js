import assert from 'node:assert/strict'

import { MessageProcessor } from '../messageProcessor.js'

const databases = [{ name: '财税库' }]

const run = () => {
  const conv = {
    messages: [
      {
        type: 'ai',
        tool_calls: [
          {
            name: '财税库',
            tool_call_result: {
              content: JSON.stringify([
                {
                  content: 'A',
                  score: 0.9,
                  metadata: { source: 'doc-a', chunk_id: 'c1', file_id: 'f1', chunk_index: 1 }
                },
                {
                  content: 'A',
                  score: 0.8,
                  metadata: { source: 'doc-a', chunk_id: 'c1', file_id: 'f1', chunk_index: 1 }
                }
              ])
            }
          },
          {
            name: 'not_kb_tool',
            tool_call_result: {
              content: JSON.stringify([{ content: 'X', score: 0.99, metadata: { chunk_id: 'cx' } }])
            }
          }
        ]
      }
    ]
  }

  const chunks = MessageProcessor.extractKnowledgeChunksFromConversation(conv, databases)

  // 1. OpenViking 数组提取
  assert.equal(
    chunks.some((c) => c.content === 'A' && c.kb_name === '财税库'),
    true
  )

  // 2. 非知识库工具忽略
  assert.equal(
    chunks.some((c) => c.content === 'X'),
    false
  )

  // 3. 去重生效（chunk_id=c1 仅一条）
  assert.equal(chunks.filter((c) => c.metadata?.chunk_id === 'c1').length, 1)

  console.log('messageProcessor extractKnowledgeChunksFromConversation: all assertions passed')
}

run()
