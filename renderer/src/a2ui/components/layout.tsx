import { createComponentImplementation } from '@a2ui/react/v0_9'
import { CommonSchemas } from '@a2ui/web_core/v0_9'
import { z } from 'zod'
import { ChildList } from '@/a2ui/ChildList'
import { cn } from '@/lib/utils'

const justifyClass: Record<string, string> = {
  start: 'justify-start',
  center: 'justify-center',
  end: 'justify-end',
  spaceBetween: 'justify-between',
  spaceAround: 'justify-around',
  spaceEvenly: 'justify-evenly',
  stretch: 'justify-stretch',
}

const alignClass: Record<string, string> = {
  start: 'items-start',
  center: 'items-center',
  end: 'items-end',
  stretch: 'items-stretch',
}

export const Column = createComponentImplementation(
  {
    name: 'Column',
    schema: z
      .object({
        children: CommonSchemas.ChildList,
        justify: z
          .enum(['start', 'center', 'end', 'spaceBetween', 'spaceAround', 'spaceEvenly', 'stretch'])
          .optional(),
        align: z.enum(['start', 'center', 'end', 'stretch']).optional(),
      })
      .strict(),
  },
  ({ props, buildChild }) => (
    <div
      className={cn(
        'flex flex-col gap-3',
        justifyClass[String(props.justify ?? 'start')],
        alignClass[String(props.align ?? 'stretch')],
      )}
    >
      <ChildList childList={props.children as never} buildChild={buildChild} />
    </div>
  ),
)

export const Row = createComponentImplementation(
  {
    name: 'Row',
    schema: z
      .object({
        children: CommonSchemas.ChildList,
        justify: z
          .enum(['start', 'center', 'end', 'spaceBetween', 'spaceAround', 'spaceEvenly', 'stretch'])
          .optional(),
        align: z.enum(['start', 'center', 'end', 'stretch']).optional(),
      })
      .strict(),
  },
  ({ props, buildChild }) => (
    <div
      className={cn(
        'flex flex-row flex-wrap gap-3',
        justifyClass[String(props.justify ?? 'start')],
        alignClass[String(props.align ?? 'center')],
      )}
    >
      <ChildList childList={props.children as never} buildChild={buildChild} />
    </div>
  ),
)
