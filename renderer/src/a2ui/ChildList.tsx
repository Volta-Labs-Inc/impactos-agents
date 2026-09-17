import type { ComponentId } from '@a2ui/web_core/v0_9'
import { Fragment, type ReactNode } from 'react'

type ResolvedChildRef =
  | ComponentId
  | {
      id: ComponentId
      basePath: string
    }

export function ChildList({
  childList,
  buildChild,
}: {
  childList: ResolvedChildRef[] | undefined
  buildChild: (id: ComponentId, basePath?: string) => ReactNode
}) {
  if (!Array.isArray(childList)) return null

  return (
    <>
      {childList.map((childRef, index) => {
        if (typeof childRef === 'string') {
          return <Fragment key={`${childRef}-${index}`}>{buildChild(childRef)}</Fragment>
        }
        return (
          <Fragment key={`${childRef.id}-${childRef.basePath}`}>
            {buildChild(childRef.id, childRef.basePath)}
          </Fragment>
        )
      })}
    </>
  )
}
