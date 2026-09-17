import { createComponentImplementation } from '@a2ui/react/v0_9'
import { CommonSchemas } from '@a2ui/web_core/v0_9'
import { z } from 'zod'
import {
  Select as UiSelect,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'

export const Select = createComponentImplementation(
  {
    name: 'Select',
    schema: z
      .object({
        label: CommonSchemas.DynamicString,
        value: CommonSchemas.DynamicString.optional(),
        placeholder: CommonSchemas.DynamicString.optional(),
        options: z
          .array(
            z
              .object({
                label: CommonSchemas.DynamicString,
                value: z.string(),
              })
              .strict(),
          )
          .min(1),
      })
      .strict(),
  },
  ({ props }) => (
    <div className="flex flex-col gap-2">
      <Label>{props.label}</Label>
      <UiSelect
        value={props.value || undefined}
        onValueChange={(next) => props.setValue?.(next)}
      >
        <SelectTrigger>
          <SelectValue placeholder={props.placeholder ?? 'Select'} />
        </SelectTrigger>
        <SelectContent>
          {props.options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {typeof option.label === 'string' ? option.label : ''}
            </SelectItem>
          ))}
        </SelectContent>
      </UiSelect>
    </div>
  ),
)
