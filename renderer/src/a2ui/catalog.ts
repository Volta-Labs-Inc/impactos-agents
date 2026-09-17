import type { ReactComponentImplementation } from '@a2ui/react/v0_9'
import { Catalog } from '@a2ui/web_core/v0_9'
import { SHADCN_CATALOG_ID } from '@/a2ui/catalog-id'
import { Button } from '@/a2ui/components/Button'
import { Card } from '@/a2ui/components/Card'
import { Input } from '@/a2ui/components/Input'
import { Column, Row } from '@/a2ui/components/layout'
import { Select } from '@/a2ui/components/Select'
import { Table } from '@/a2ui/components/Table'
import { Text } from '@/a2ui/components/Text'

export const shadcnCatalog = new Catalog<ReactComponentImplementation>(SHADCN_CATALOG_ID, [
  Column,
  Row,
  Text,
  Card,
  Button,
  Input,
  Select,
  Table,
])
