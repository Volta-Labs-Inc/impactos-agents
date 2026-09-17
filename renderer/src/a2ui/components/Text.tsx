import { createComponentImplementation } from '@a2ui/react/v0_9'
import { CommonSchemas } from '@a2ui/web_core/v0_9'
import { z } from 'zod'
import { cn } from '@/lib/utils'

const variantClass: Record<string, string> = {
  h1: 'text-2xl font-medium tracking-tight text-foreground',
  h2: 'text-lg font-medium tracking-tight text-foreground',
  h3: 'text-base font-medium text-foreground',
  body: 'text-sm leading-6 text-foreground',
  muted: 'text-sm text-muted-foreground',
}

export const Text = createComponentImplementation(
  {
    name: 'Text',
    schema: z
      .object({
        text: CommonSchemas.DynamicString,
        variant: z.enum(['h1', 'h2', 'h3', 'body', 'muted']).optional(),
      })
      .strict(),
  },
  ({ props }) => {
    const variant = props.variant ?? 'body'
    const Tag = variant === 'h1' ? 'h1' : variant === 'h2' ? 'h2' : variant === 'h3' ? 'h3' : 'p'
    return <Tag className={cn(variantClass[variant])}>{props.text}</Tag>
  },
)
