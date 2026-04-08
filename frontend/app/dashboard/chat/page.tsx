'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAssets } from '@/lib/api'
import { useAgentStream } from '@/lib/websocket'
import { PageHeader, AlertBadge } from '@/components/ui'
import {
  Send, Bot, User, Zap, ChevronDown,
  BookOpen, Radio, RotateCcw, Cpu,
} from 'lucide-react'
import { clsx } from 'clsx'
import { formatDistanceToNow } from 'date-fns'

interface Message {
  id:       string
  role:     'user' | 'assistant'
  content:  string
  sources?: Source[]
  ts:       Date
  streaming?: boolean
}

interface Source {
  score:    number
  title:    string
  section:  string
  category: string
}

const SESSION_ID = `session-${Math.random().toString(36).slice(2, 9)}`

const STARTERS = [
  'Why is TRB-001 vibrating above threshold?',
  'What does bearing temperature rising mean for a turbine?',
  'How should I respond to a lube oil pressure drop?',
  'Summarise active failures across all assets.',
  'What are the steps for emergency turbine shutdown?',
  'Predict which assets are most at risk this week.',
]

export default function ChatPage() {
  const [messages, setMessages]   = useState<Message[]>([])
  const [input,    setInput]      = useState('')
  const [assetId,  setAssetId]    = useState<string>('')
  const [showSrc,  setShowSrc]    = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)

  const assets = useQuery({ queryKey: ['assets'], queryFn: getAssets })
  const { status, streaming, buffer, sources, sendMessage, reset } = useAgentStream(SESSION_ID)

  // Scroll to bottom whenever messages or buffer change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, buffer])

  // When streaming finishes, commit the buffered response as a real message
  useEffect(() => {
    if (!streaming && buffer) {
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.streaming) {
          return [
            ...prev.slice(0, -1),
            { ...last, content: buffer, sources, streaming: false },
          ]
        }
        return prev
      })
      reset()
    }
  }, [streaming, buffer, sources, reset])

  // While streaming, update the placeholder message live
  useEffect(() => {
    if (streaming && buffer) {
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.streaming) {
          return [...prev.slice(0, -1), { ...last, content: buffer }]
        }
        return prev
      })
    }
  }, [buffer, streaming])

  const send = useCallback(() => {
    const text = input.trim()
    if (!text || streaming) return

    const userMsg: Message = {
      id: Date.now().toString(), role: 'user', content: text, ts: new Date(),
    }
    const placeholderMsg: Message = {
      id: (Date.now() + 1).toString(), role: 'assistant',
      content: '', ts: new Date(), streaming: true,
    }

    setMessages(prev => [...prev, userMsg, placeholderMsg])
    setInput('')

    const history = messages.map(m => ({ role: m.role, content: m.content }))
    sendMessage(text, assetId || undefined, history)
  }, [input, streaming, messages, assetId, sendMessage])

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  function clearChat() { setMessages([]); reset() }

  return (
    <div className="flex flex-col h-[calc(100vh-0px)] animate-fade-in">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-bg-border shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink flex items-center gap-2">
              <Cpu size={18} className="text-brand" />
              AI Co-pilot
            </h1>
            <p className="text-xs text-ink-muted font-mono mt-0.5">
              Powered by Claude · RAG over plant documentation
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Asset scope selector */}
            <div className="relative">
              <select
                value={assetId}
                onChange={e => setAssetId(e.target.value)}
                className="appearance-none bg-bg-raised border border-bg-border rounded-lg pl-3 pr-8 py-1.5 text-xs font-mono text-ink-muted focus:outline-none focus:border-brand/40 cursor-pointer">
                <option value="">All assets</option>
                {assets.data?.map(a => (
                  <option key={a.asset_id} value={a.asset_id}>{a.asset_id}</option>
                ))}
              </select>
              <ChevronDown size={11} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-faint pointer-events-none" />
            </div>

            {/* WS status */}
            <div className={clsx(
              'flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1.5 rounded-lg border',
              status === 'connected' ? 'text-ok border-ok/20 bg-ok/5' : 'text-ink-faint border-bg-border',
            )}>
              <Radio size={9} />
              {status === 'connected' ? 'CONNECTED' : status.toUpperCase()}
            </div>

            <button onClick={clearChat}
              className="p-1.5 rounded-lg border border-bg-border text-ink-faint hover:text-ink hover:bg-bg-raised transition-colors">
              <RotateCcw size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5 scroll-area">
        {messages.length === 0 ? (
          <WelcomeScreen starters={STARTERS} onSelect={s => { setInput(s); inputRef.current?.focus() }} />
        ) : (
          messages.map(m => (
            <MessageBubble key={m.id} message={m}
              showSources={showSrc === m.id}
              onToggleSources={() => setShowSrc(showSrc === m.id ? null : m.id)}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 pb-6 pt-3 border-t border-bg-border shrink-0">
        {assetId && (
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-mono text-brand bg-brand/10 border border-brand/20 px-2 py-0.5 rounded">
              Scoped to {assetId}
            </span>
            <button onClick={() => setAssetId('')} className="text-[10px] text-ink-faint hover:text-ink font-mono">
              × clear
            </button>
          </div>
        )}
        <div className={clsx(
          'flex items-end gap-3 bg-bg-raised border rounded-xl px-4 py-3 transition-colors',
          streaming ? 'border-brand/30' : 'border-bg-border focus-within:border-brand/40',
        )}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
            disabled={streaming}
            placeholder={streaming ? 'Waiting for response...' : 'Ask about any asset, failure, or procedure...'}
            className="flex-1 bg-transparent text-sm text-ink placeholder:text-ink-faint resize-none focus:outline-none leading-relaxed"
            style={{ maxHeight: 120, overflowY: 'auto' }}
          />
          <button onClick={send} disabled={!input.trim() || streaming}
            className={clsx(
              'shrink-0 p-2 rounded-lg transition-all',
              input.trim() && !streaming
                ? 'bg-brand text-bg-base hover:bg-brand/90 active:scale-95'
                : 'bg-bg-muted text-ink-faint cursor-not-allowed'
            )}>
            {streaming
              ? <span className="w-4 h-4 block border-2 border-brand/30 border-t-brand rounded-full animate-spin" />
              : <Send size={15} />}
          </button>
        </div>
        <p className="text-[10px] text-ink-faint font-mono mt-2 text-center">
          Enter to send · Shift+Enter for new line · Responses stream token-by-token
        </p>
      </div>
    </div>
  )
}

// ── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ message, showSources, onToggleSources }: {
  message: Message; showSources: boolean; onToggleSources: () => void
}) {
  const isUser = message.role === 'user'
  return (
    <div className={clsx('flex gap-3 animate-slide-in', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div className={clsx(
        'w-7 h-7 rounded-xl flex items-center justify-center shrink-0 mt-0.5',
        isUser ? 'bg-brand/10 border border-brand/20' : 'bg-bg-raised border border-bg-border'
      )}>
        {isUser ? <User size={13} className="text-brand" /> : <Bot size={13} className="text-ink-muted" />}
      </div>

      {/* Content */}
      <div className={clsx('max-w-[80%] space-y-2', isUser && 'items-end flex flex-col')}>
        <div className={isUser ? 'bubble-user' : 'bubble-ai'}>
          {message.streaming && !message.content ? (
            <span className="flex gap-1 py-1">
              {[0,1,2].map(i => (
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-pulse"
                  style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </span>
          ) : (
            <MarkdownContent
              content={message.content}
              streaming={message.streaming}
            />
          )}
        </div>

        {/* Sources + timestamp */}
        <div className={clsx('flex items-center gap-3', isUser && 'flex-row-reverse')}>
          <span className="text-[10px] text-ink-faint font-mono">
            {formatDistanceToNow(message.ts, { addSuffix: true })}
          </span>
          {!isUser && message.sources && message.sources.length > 0 && (
            <button onClick={onToggleSources}
              className="flex items-center gap-1 text-[10px] font-mono text-brand/70 hover:text-brand transition-colors">
              <BookOpen size={10} />
              {message.sources.length} source{message.sources.length !== 1 ? 's' : ''}
            </button>
          )}
        </div>

        {/* Sources dropdown */}
        {showSources && message.sources && (
          <div className="w-full space-y-1.5 animate-slide-in">
            {message.sources.map((s, i) => (
              <div key={i} className="bg-bg-raised border border-bg-border rounded-lg px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-mono text-brand">[{i + 1}]</span>
                  <span className="text-[10px] font-mono text-ink-faint">{s.category}</span>
                  <span className="ml-auto text-[10px] font-mono text-ok">
                    {(s.score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-xs text-ink font-medium leading-snug">{s.title}</p>
                <p className="text-[10px] text-ink-muted mt-0.5">{s.section}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Minimal markdown renderer ─────────────────────────────────────────────────

function MarkdownContent({ content, streaming }: { content: string; streaming?: boolean }) {
  // Very lightweight: bold, inline code, numbered lists, bullet points
  const lines = content.split('\n')
  return (
    <div className={clsx('space-y-1.5 text-sm leading-relaxed', streaming && 'cursor-blink')}>
      {lines.map((line, i) => {
        if (!line.trim()) return <br key={i} />

        // Headings
        if (line.startsWith('## ')) return (
          <p key={i} className="font-semibold text-ink mt-2">{line.slice(3)}</p>
        )

        // Numbered list
        const numMatch = line.match(/^(\d+)\.\s+(.*)/)
        if (numMatch) return (
          <div key={i} className="flex gap-2">
            <span className="text-brand font-mono text-[11px] shrink-0 mt-0.5">{numMatch[1]}.</span>
            <span>{renderInline(numMatch[2])}</span>
          </div>
        )

        // Bullet
        if (line.startsWith('- ') || line.startsWith('* ')) return (
          <div key={i} className="flex gap-2">
            <span className="text-ink-faint shrink-0 mt-1">·</span>
            <span>{renderInline(line.slice(2))}</span>
          </div>
        )

        return <p key={i}>{renderInline(line)}</p>
      })}
    </div>
  )
}

function renderInline(text: string) {
  // Bold **text** and `code`
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/)
  return (
    <>
      {parts.map((p, i) => {
        if (p.startsWith('**') && p.endsWith('**'))
          return <strong key={i} className="font-semibold text-ink">{p.slice(2, -2)}</strong>
        if (p.startsWith('`') && p.endsWith('`'))
          return <code key={i} className="font-mono text-[11px] bg-bg-base border border-bg-border rounded px-1 py-0.5 text-brand">{p.slice(1, -1)}</code>
        return p
      })}
    </>
  )
}

// ── Welcome / empty state ─────────────────────────────────────────────────────

function WelcomeScreen({ starters, onSelect }: { starters: string[]; onSelect: (s: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-12 space-y-8">
      <div className="text-center space-y-2">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-brand/10 border border-brand/20 mb-2">
          <Zap size={24} className="text-brand" />
        </div>
        <h2 className="text-lg font-semibold text-ink">AI Operations Co-pilot</h2>
        <p className="text-sm text-ink-muted max-w-sm text-center">
          Ask about sensor anomalies, maintenance procedures, failure patterns, or any operational question.
        </p>
      </div>

      <div className="w-full max-w-lg space-y-2">
        <p className="text-[10px] font-mono text-ink-faint uppercase tracking-widest text-center mb-3">
          Suggested questions
        </p>
        {starters.map(s => (
          <button key={s} onClick={() => onSelect(s)}
            className="w-full text-left text-sm text-ink-muted hover:text-ink px-4 py-2.5 rounded-xl border border-bg-border hover:border-brand/30 hover:bg-brand/5 transition-all bg-bg-surface">
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
