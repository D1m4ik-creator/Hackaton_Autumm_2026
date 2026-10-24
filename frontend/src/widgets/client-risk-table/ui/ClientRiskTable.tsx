import { Alert, Button, Empty, Table } from 'antd'
import type { TableColumnsType, TableProps } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ClientRiskIndicator } from '../../../entities/client'
import { getCustomers } from '../../../api/customers'
import { useApiResource } from '../../../api/useApiResource'
import type { Client } from '../../../entities/client'
import { useClientFiltersStore } from '../../../features/filter-clients'
import type { ClientSortField } from '../../../features/filter-clients'
import { clientDetailPath } from '../../../shared/lib/app-paths'
import { formatEuro, formatEuroCents } from '../../../shared/lib/format'
import './client-risk-table.css'

export function ClientRiskTable() {
  const filters = useClientFiltersStore()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [search, setSearch] = useState(filters.search)
  useEffect(() => {
    const timer = setTimeout(() => setSearch(filters.search.trim()), 300)
    return () => clearTimeout(timer)
  }, [filters.search])
  const queryKey = `${filters.risk}|${search}|${filters.sortField}|${filters.sortOrder}`
  const [pagination, setPagination] = useState({ key: queryKey, page: 1, pageSize: 50 })
  const page = pagination.key === queryKey ? pagination.page : 1
  const { pageSize } = pagination
  const loader = useCallback(() => getCustomers({
    level: filters.risk === 'all' ? undefined : filters.risk,
    search: search || undefined,
    sort: filters.sortField ?? 'riskScore', order: filters.sortOrder === 'ascend' ? 'asc' : 'desc', page, pageSize,
  }), [filters.risk, filters.sortField, filters.sortOrder, search, page, pageSize])
  const { data, loading, error, reload } = useApiResource(loader)

  if (data && page > 1 && (page - 1) * pageSize >= data.total) {
    setPagination({ key: queryKey, page: Math.max(1, Math.ceil(data.total / pageSize)), pageSize })
  }

  function openClient(client: Client) {
    navigate(clientDetailPath(pathname, client.accountId))
  }

  const sortable = (field: ClientSortField) => ({
    key: field,
    sorter: true,
    sortOrder: filters.sortField === field ? filters.sortOrder : null,
    sortIcon: ({ sortOrder }: { sortOrder?: 'ascend' | 'descend' | null }) => <span className={`client-sort-icon ${sortOrder ? 'client-sort-icon--active' : ''}`} aria-hidden="true">{sortOrder === 'ascend' ? '↑' : sortOrder === 'descend' ? '↓' : '↕'}</span>,
  })

  const columns: TableColumnsType<Client> = [
    { ...sortable('id'), title: 'ID', dataIndex: 'accountId', width: 98, className: 'client-id-column', render: (id: number) => `#${id}` },
    { ...sortable('email'), title: 'EMAIL', dataIndex: 'email', width: 270,
      render: (_, client) => <div>
        <Link className="client-table-link" to={clientDetailPath(pathname, client.accountId)} title={client.email} aria-label={`Открыть клиента ${client.email}`} onClick={(event) => event.stopPropagation()}>{client.email}</Link>
        {client.reason && <p className="client-table-reason">{client.reason}</p>}
      </div> },
    { ...sortable('balance'), title: 'БАЛАНС', dataIndex: 'balanceCents', width: 144, align: 'center', render: formatEuroCents },
    { ...sortable('totalReplenished'), title: 'ПОПОЛНЕНИЯ', dataIndex: 'totalReplenishedCents', width: 160, align: 'center', render: formatEuroCents },
    { ...sortable('expectedLossCents'), title: 'ПОТЕРИ, €', dataIndex: 'revenueAtRisk', width: 140, align: 'center', render: formatEuro },
    { ...sortable('riskScore'), title: 'RISK', dataIndex: 'score', align: 'right', className: 'client-risk-column', render: (_, client) => <ClientRiskIndicator client={client} /> },
  ]

  const handleChange: TableProps<Client>['onChange'] = (nextPage, __, sorter, extra) => {
    const selectedSort = Array.isArray(sorter) ? sorter[0] : sorter
    filters.setSort(selectedSort.order ? selectedSort.columnKey as ClientSortField : null, selectedSort.order ?? null)
    setPagination({ key: extra.action === 'sort' ? '' : queryKey, page: nextPage.current ?? 1, pageSize: nextPage.pageSize ?? pageSize })
  }

  return (
    <section className="client-risk-table" aria-label="Таблица клиентов под риском">
      {error && <Alert type="error" showIcon title="Не удалось загрузить клиентов" description={error} action={<Button onClick={reload}>Повторить</Button>} />}
      <Table<Client>
        rowKey="id"
        tableLayout="fixed"
        columns={columns}
        dataSource={data?.items ?? []}
        loading={loading}
        pagination={{ current: page, pageSize, total: data?.total ?? 0, showSizeChanger: true, pageSizeOptions: [20, 50, 100, 200] }}
        showSorterTooltip={false}
        onChange={handleChange}
        onRow={(client) => ({ onClick: () => openClient(client) })}
        scroll={{ x: 1040 }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Нет клиентов с выбранным уровнем риска" /> }}
      />
      <span className="visually-hidden" role="status" aria-live="polite">Показано клиентов: {data?.items.length ?? 0} из {data?.total ?? 0}</span>
    </section>
  )
}
