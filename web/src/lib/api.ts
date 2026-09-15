/** API 客户端：真实调用后端分页接口。 */
import type { PaginateRequest, PaginateResponse } from './types'

export async function paginate(request: PaginateRequest): Promise<PaginateResponse> {
  const res = await fetch('/api/paginate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const detail =
      body !== null && typeof body === 'object' && 'detail' in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`
    throw new Error(`分页请求失败：${detail}`)
  }
  return body as PaginateResponse
}
