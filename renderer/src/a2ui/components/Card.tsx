import { createComponentImplementation } from '@a2ui/react/v0_9'
import { CommonSchemas } from '@a2ui/web_core/v0_9'
import { z } from 'zod'
import { Card as UiCard, CardContent } from '@/components/ui/card'

export const Card = createComponentImplementation(
  {
    name: 'Card',
    schema: z
      .object({
        child: CommonSchemas.ComponentId.describe(
          'ID of the single child. Wrap multiple children in a Column or Row.',
        ),
      })
      .strict(),
  },
  ({ props, buildChild }) => (
    <UiCard>
      <CardContent className="p-5">{props.child ? buildChild(props.child) : null}</CardContent>
    </UiCard>
  ),
)
