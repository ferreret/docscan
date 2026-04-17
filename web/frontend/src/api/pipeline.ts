import { api } from '@/api/client'
import type { PipelineResponse, PipelineStep } from '@/api/types-pipeline'

export const pipelineApi = {
  get: (appId: number) =>
    api.get<PipelineResponse>(`/applications/${appId}/pipeline`),

  put: (appId: number, steps: PipelineStep[]) =>
    api.put<PipelineResponse>(`/applications/${appId}/pipeline`, { steps }),
}
