import { createComponentImplementation } from '@a2ui/react/v0_9'
import { CommonSchemas } from '@a2ui/web_core/v0_9'
import { z } from 'zod'
import {
  Table as UiTable,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export const Table = createComponentImplementation(
  {
    name: 'Table',
    schema: z
      .object({
        caption: CommonSchemas.DynamicString.optional(),
        columns: z
          .array(
            z
              .object({
                key: z.string(),
                label: CommonSchemas.DynamicString,
              })
              .strict(),
          )
          .min(1),
        rows: CommonSchemas.DynamicValue.describe(
          'Array of objects. Bind to a data-model path like /items.',
        ),
      })
      .strict(),
  },
  ({ props }) => {
    const rows = Array.isArray(props.rows) ? props.rows : []

    return (
      <UiTable>
        {props.caption ? <TableCaption>{props.caption}</TableCaption> : null}
        <TableHeader>
          <TableRow>
            {props.columns.map((column) => (
              <TableHead key={column.key}>
                {typeof column.label === 'string' ? column.label : ''}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => {
            const record =
              row && typeof row === 'object' && !Array.isArray(row)
                ? (row as Record<string, unknown>)
                : {}
            return (
              <TableRow key={index}>
                {props.columns.map((column) => (
                  <TableCell key={column.key}>{String(record[column.key] ?? '')}</TableCell>
                ))}
              </TableRow>
            )
          })}
        </TableBody>
      </UiTable>
    )
  },
)
