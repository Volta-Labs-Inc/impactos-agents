import { createComponentImplementation } from '@a2ui/react/v0_9'
import { CommonSchemas } from '@a2ui/web_core/v0_9'
import { z } from 'zod'
import { Button as UiButton } from '@/components/ui/button'

export const Button = createComponentImplementation(
  {
    name: 'Button',
    schema: z
      .object({
        label: CommonSchemas.DynamicString,
        variant: z.enum(['default', 'primary', 'outline', 'ghost']).optional(),
        action: CommonSchemas.Action.optional(),
      })
      .strict(),
  },
  ({ props }) => {
    const variant =
      props.variant === 'primary'
        ? 'default'
        : props.variant === 'outline'
          ? 'outline'
          : props.variant === 'ghost'
            ? 'ghost'
            : 'secondary'

    return (
      <UiButton type="button" variant={variant} onClick={props.action}>
        {props.label}
      </UiButton>
    )
  },
)
