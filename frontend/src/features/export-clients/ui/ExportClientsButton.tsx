import { useState } from 'react'
import { Button, Dropdown } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { exportCustomers } from '../../../api/customers'
import type { CustomerExportFormat } from '../../../api/customers'
import { useClientFiltersStore } from '../../filter-clients'

const formats: { key: CustomerExportFormat; label: string }[] = [
  { key: 'xlsx', label: 'Excel (.xlsx)' },
  { key: 'csv', label: 'CSV (.csv)' },
  { key: 'json', label: 'JSON (.json)' },
]

// Выгружает всех клиентов под текущими фильтром, поиском и сортировкой таблицы (без пагинации)
export function ExportClientsButton() {
  const filters = useClientFiltersStore()
  const [loading, setLoading] = useState(false)

  async function download(format: CustomerExportFormat) {
    setLoading(true)
    try {
      await exportCustomers(format, {
        level: filters.risk === 'all' ? undefined : filters.risk,
        search: filters.search.trim() || undefined,
        sort: filters.sortField ?? 'riskScore',
        order: filters.sortOrder === 'ascend' ? 'asc' : 'desc',
      })
    } catch {
      // Ошибку уже показал перехватчик http
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dropdown menu={{ items: formats, onClick: ({ key }) => void download(key as CustomerExportFormat) }} trigger={['click']} disabled={loading}>
      <Button className="export-clients-button" icon={<DownloadOutlined />} loading={loading}>Выгрузить</Button>
    </Dropdown>
  )
}
