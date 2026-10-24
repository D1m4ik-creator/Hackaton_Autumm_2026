import { ArrowLeftOutlined, SearchOutlined } from '@ant-design/icons'
import { Alert, Button, Descriptions, Drawer, Empty, Input, Select, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { mockClients, RiskBadge, riskLabels } from '../../../entities/client'
import type { Client, RiskLevel } from '../../../entities/client'
import { formatEuro } from '../../../shared/lib/format'
import { useExploreClientsStore } from '../model/store'
import './clients-drawer.css'

const columns: TableColumnsType<Client> = [
  { title: 'Клиент', dataIndex: 'name', render: (_, client) => <div className="client-cell"><strong>{client.name}</strong><span>{client.email}</span></div> },
  { title: 'Риск', dataIndex: 'risk', render: (risk: RiskLevel) => <RiskBadge level={risk} /> },
  { title: 'Risk-score', dataIndex: 'score', sorter: (a, b) => a.score - b.score, render: (value: number) => `${value}%` },
  { title: 'Под угрозой', dataIndex: 'revenueAtRisk', align: 'right', sorter: (a, b) => a.revenueAtRisk - b.revenueAtRisk, render: formatEuro },
  { title: '', key: 'action', render: (_, client) => <Button type="link" onClick={() => useExploreClientsStore.getState().selectClient(client.id)} aria-label={`Открыть клиента ${client.name}`}>Открыть</Button> },
]

export function ClientsDrawer() {
  const { isOpen, query, riskFilter, selectedClientId, closeClients, setQuery, setRiskFilter, selectClient } = useExploreClientsStore()
  const selected = mockClients.find((client) => client.id === selectedClientId)
  const clients = mockClients.filter((client) =>
    (riskFilter === 'all' || client.risk === riskFilter)
    && `${client.name} ${client.email}`.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru')),
  )

  return (
    <Drawer title={selected ? selected.name : 'Клиенты под риском'} open={isOpen} onClose={closeClients} size={800}>
      <Alert type="info" showIcon title="Демонстрационные данные" description={`В списке показаны ${mockClients.length} примеров клиентов. Сводные показатели представляют всю базу из макета.`} className="demo-note" />
      {selected ? (
        <>
          <Button icon={<ArrowLeftOutlined />} onClick={() => selectClient(null)} className="back-to-clients">К списку клиентов</Button>
          <Descriptions column={1} bordered items={[
            { key: 'id', label: 'ID', children: selected.id },
            { key: 'email', label: 'Email', children: selected.email },
            { key: 'risk', label: 'Уровень риска', children: <RiskBadge level={selected.risk} /> },
            { key: 'score', label: 'Risk-score', children: `${selected.score}%` },
            { key: 'revenue', label: 'Выручка под угрозой, 30 дней', children: formatEuro(selected.revenueAtRisk) },
            { key: 'activity', label: 'Последняя активность', children: new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC' }).format(new Date(selected.lastActivity)) },
            { key: 'reason', label: 'Факторы риска', children: selected.reason },
          ]} />
        </>
      ) : (
        <>
          <div className="clients-filters">
            <Input allowClear prefix={<SearchOutlined />} placeholder="Имя или email" aria-label="Поиск клиентов" value={query} onChange={(event) => setQuery(event.target.value)} />
            <Select aria-label="Уровень риска" value={riskFilter} onChange={setRiskFilter} options={[
              { value: 'all', label: 'Все уровни' },
              ...Object.entries(riskLabels).map(([value, label]) => ({ value, label })),
            ]} />
          </div>
          <Table<Client> rowKey="id" columns={columns} dataSource={clients} pagination={false} scroll={{ x: 650 }} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Клиенты не найдены" /> }} />
        </>
      )}
    </Drawer>
  )
}
