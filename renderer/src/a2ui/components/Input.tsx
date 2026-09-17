import { createComponentImplementation } from '@a2ui/react/v0_9'
import { CommonSchemas } from '@a2ui/web_core/v0_9'
import { useId } from 'react'
import { z } from 'zod'
import { Input as UiInput } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export const Input = createComponentImplementation(
  {
    name: 'Input',
    schema: z
      .object({
        label: CommonSchemas.DynamicString,
        value: CommonSchemas.DynamicString.optional(),
        placeholder: CommonSchemas.DynamicString.optional(),
      })
      .strict(),
  },
  ({ props }) => {
    const id = useId()
    return (
      <div className="flex flex-col gap-2">
        <Label htmlFor={id}>{props.label}</Label>
        <UiInput
          id={id}
          value={props.value ?? ''}
          placeholder={props.placeholder}
          onChange={(event) => props.setValue?.(event.target.value)}
        />
      </div>
    )
  },
)
