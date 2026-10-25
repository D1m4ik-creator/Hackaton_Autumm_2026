import { Alert, Empty, Spin, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { isAxiosError } from 'axios'
import { getPublicCustomers, getPublicSummary } from '../../../api/public-report'
import type { PublicCustomerItem, PublicSummary } from '../../../api/public-report'
import { RiskBadge } from '../../../entities/client'
import { AezaLogo } from '../../../shared/ui/aeza-logo/AezaLogo'
import { formatEuro, formatEuroCents } from '../../../shared/lib/format'
import './public-report.css'

function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    if (error.response?.status === 401) return 'Эта ссылка недействительна, отозвана или истекла.'
    if (error.response?.status === 429) return 'Слишком много запросов. Попробуйте позже.'
  }
  return 'Не удалось загрузить отчёт.'
}

export function PublicReportPage() {
  const { token = '' } = useParams<{ token: string }>()
  const [summary, setSummary] = useState<PublicSummary | null>(null)
  const [customers, setCustomers] = useState<PublicCustomerItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([
      getPublicSummary(token),
      getPublicCustomers(token, { sort: 'expectedLossCents', order: 'desc', pageSize: 200 }),
    ]).then(([summaryRes, customersRes]) => {
      if (!active) return
      setSummary(summaryRes)
      setCustomers(customersRes.items)
    }).catch((err: unknown) => { if (active) setError(errorMessage(err)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token])

  const columns: TableColumnsType<PublicCustomerItem> = [
    { title: 'ID', dataIndex: 'id', width: 90, render: (id: number) => `#${id}` },
    { title: 'БАЛАНС', dataIndex: 'balance', align: 'center', render: formatEuroCents },
    { title: 'ПОПОЛНЕНИЯ', dataIndex: 'totalReplenished', align: 'center', render: formatEuroCents },
    { title: 'ПОТЕРИ, €', dataIndex: 'expectedLossCents', align: 'center', render: formatEuroCents },
    { title: 'RISK', dataIndex: 'level', align: 'right', render: (level: PublicCustomerItem['level']) => <RiskBadge level={level} /> },
  ]

  return (
    <div className="public-report">
      <header className="public-report__header">
        <AezaLogo className="public-report__logo" />
        <h1>Отчёт по риску оттока</h1>
        <p>Публичная read-only ссылка — без входа в панель.</p>
      </header>

      {loading && <Spin className="public-report__spin" />}
      {error && <Alert type="error" showIcon title={error} role="alert" />}

      {!loading && !error && summary && <>
        <section className="public-report-stats" aria-label="Сводка">
          <div className="public-report-stat">
            <span className="public-report-stat__label">КЛИЕНТОВ</span>
            <span className="public-report-stat__value">{summary.customersTotal}</span>
          </div>
          <div className="public-report-stat">
            <span className="public-report-stat__label">ОЖИДАЕМЫЕ ПОТЕРИ</span>
            <span className="public-report-stat__value">{formatEuro(summary.expectedLossCents / 100)}</span>
          </div>
          <div className="public-report-stat">
            <span className="public-report-stat__label">ВЫСОКИЙ РИСК</span>
            <span className="public-report-stat__value">{summary.byLevel.high.customers}</span>
          </div>
        </section>

        <Table<PublicCustomerItem>
          rowKey="id"
          columns={columns}
          dataSource={customers}
          pagination={false}
          scroll={{ x: 700 }}
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Нет данных" /> }}
        />
      </>}
    </div>
  )
}
