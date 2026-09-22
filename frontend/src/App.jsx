import { useState } from 'react'
import './App.css'

const sampleQuestions = [
  'FPT thuộc ngành nào?',
  'Tổng tài sản FPT quý 2/2026 là bao nhiêu?',
  'Nợ phải trả FPT quý 2/2026 là bao nhiêu?',
  'Vốn chủ sở hữu FPT quý 2/2026 là bao nhiêu?',
  'FPT có những kỳ báo cáo nào?',
  'So sánh tổng tài sản FPT giữa hai kỳ gần nhất.',
]

function App() {
  const [question, setQuestion] = useState(sampleQuestions[1])
  const [cypher, setCypher] = useState('')
  const [records, setRecords] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function ask(event) {
    event.preventDefault()
    const normalizedQuestion = question.trim()
    if (!normalizedQuestion || loading) return

    setLoading(true)
    setCypher('')
    setRecords([])
    setError('')
    try {
      const response = await fetch('/api/graph/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: normalizedQuestion }),
      })
      const body = await response.json()
      if (!response.ok) {
        throw new Error(body.detail ? JSON.stringify(body.detail) : `HTTP ${response.status}`)
      }
      setCypher(body.cypher ?? '')
      setRecords(body.records ?? [])
      setError(body.error ?? '')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Không thể gọi API')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="shell">
      <header className="intro">
        <p className="eyebrow">FinMind · Knowledge Graph Lab</p>
        <h1>Natural language → Cypher → Neo4j</h1>
        <p>
          Prototype này hiển thị câu Cypher do LLM sinh và records thô từ graph.
          Nó chưa tạo câu trả lời tài chính cuối cùng.
        </p>
      </header>

      <section className="panel question-panel" aria-labelledby="question-title">
        <h2 id="question-title">Câu hỏi kiểm thử</h2>
        <div className="samples" aria-label="Câu hỏi mẫu">
          {sampleQuestions.map((sample) => (
            <button
              className="sample"
              key={sample}
              type="button"
              onClick={() => setQuestion(sample)}
            >
              {sample}
            </button>
          ))}
        </div>

        <form onSubmit={ask}>
          <label htmlFor="question">Nhập câu hỏi tiếng Việt</label>
          <div className="ask-row">
            <input
              id="question"
              value={question}
              maxLength={1000}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ví dụ: Tổng tài sản FPT quý 2/2026 là bao nhiêu?"
            />
            <button className="ask" type="submit" disabled={loading || !question.trim()}>
              {loading ? 'Đang hỏi…' : 'Ask'}
            </button>
          </div>
        </form>
      </section>

      <div className="output-grid" aria-live="polite">
        <section className="panel output">
          <div className="output-heading">
            <h2>Generated Cypher</h2>
            <span>read-only</span>
          </div>
          <pre>{cypher || 'Cypher sẽ xuất hiện ở đây.'}</pre>
        </section>

        <section className="panel output">
          <div className="output-heading">
            <h2>Query Result</h2>
            <span>{records.length} record(s)</span>
          </div>
          <pre>{records.length ? JSON.stringify(records, null, 2) : 'Chưa có dữ liệu trả về.'}</pre>
        </section>
      </div>

      {error && (
        <section className="error" role="alert">
          <strong>Error</strong>
          <p>{error}</p>
        </section>
      )}
    </main>
  )
}

export default App
