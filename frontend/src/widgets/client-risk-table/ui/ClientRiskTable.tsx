import { Empty, Table } from 'antd'
import type { TableColumnsType, TableProps } from 'antd'
import { useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ClientRiskIndicator, mockClients } from '../../../entities/client'
import type { Client } from '../../../entities/client'
import { filterClientsByRisk, sortClients, useClientFiltersStore } from '../../../features/filter-clients'
import type { ClientSortField } from '../../../features/filter-clients'
import { clientDetailPath } from '../../../shared/lib/app-paths'
import { formatEuro, formatEuroCents } from '../../../shared/lib/format'
import { useInfiniteList } from '../../../shared/lib/infinite-list/useInfiniteList'
import { InfiniteScrollSentinel } from '../../../shared/ui/infinite-scroll-sentinel/InfiniteScrollSentinel'
import './client-risk-table.css'

export function ClientRiskTable() {
  const filters = useClientFiltersStore()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  // Переход риск-фильтра меняет состав списка (сбрасываем пагинацию ниже),
  // а сортировка — только порядок тех же строк, поэтому считаем их отдельными
  // useMemo: инфинит-скроллу нужна стабильная ссылка именно на отфильтрованный
  // (ещё не отсортированный) список, чтобы не сбрасывать уже подгруженные
  // страницы при одной лишь смене сортировки.
  const riskFilteredClients = useMemo(
    () => filterClientsByRisk(mockClients, filters.risk),
    [filters.risk],
  )
  const sortedClients = useMemo(
    () => sortClients(riskFilteredClients, filters.sortField, filters.sortOrder),
    [riskFilteredClients, filters.sortField, filters.sortOrder],
  )
  const { visibleItems: visibleClients, hasMore, loadMore } = useInfiniteList(sortedClients, undefined, riskFilteredClients)

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
    { ...sortable('accountId'), title: 'ID', dataIndex: 'accountId', width: 98, className: 'client-id-column', render: (id: number) => `#${id}` },
    { ...sortable('name'), title: 'КЛИЕНТ / EMAIL', dataIndex: 'name', width: 270,
      render: (_, client) => <Link className="client-table-link" to={clientDetailPath(pathname, client.accountId)} title={`${client.name} · ${client.email}`} aria-label={`Открыть клиента ${client.name}`} onClick={(event) => event.stopPropagation()}>{client.name} · {client.email}</Link> },
    { ...sortable('balanceCents'), title: 'БАЛАНС', dataIndex: 'balanceCents', width: 144, align: 'center', render: formatEuroCents },
    { ...sortable('totalReplenishedCents'), title: 'ПОПОЛНЕНИЯ', dataIndex: 'totalReplenishedCents', width: 160, align: 'center', render: (cents: number) => formatEuro(cents / 100) },
    { ...sortable('score'), title: 'RISK', dataIndex: 'score', align: 'right', className: 'client-risk-column', render: (_, client) => <ClientRiskIndicator client={client} /> },
  ]

  const handleChange: TableProps<Client>['onChange'] = (_, __, sorter) => {
    const selectedSort = Array.isArray(sorter) ? sorter[0] : sorter
    filters.setSort(selectedSort.order ? selectedSort.columnKey as ClientSortField : null, selectedSort.order ?? null)
  }

  return (
    <section className="client-risk-table" aria-label="Таблица клиентов под риском">
      <Table<Client>
        rowKey="id"
        tableLayout="fixed"
        columns={columns}
        dataSource={visibleClients}
        pagination={false}
        showSorterTooltip={false}
        onChange={handleChange}
        onRow={(client) => ({ onClick: () => openClient(client) })}
        scroll={{ x: 900 }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Нет клиентов с выбранным уровнем риска" /> }}
      />
      <InfiniteScrollSentinel hasMore={hasMore} onIntersect={loadMore} />
      <span className="visually-hidden" role="status" aria-live="polite">Показано клиентов: {visibleClients.length} из {riskFilteredClients.length}</span>
    </section>
  )
}
