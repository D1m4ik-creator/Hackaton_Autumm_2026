import { Form, Input, InputNumber, Modal } from 'antd'
import { useModelSettingsStore } from '../model/store'

interface FeatureValues { name: string; weight: number }

export function AddModelFeatureModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form] = Form.useForm<FeatureValues>()
  const addFeature = useModelSettingsStore((state) => state.addFeature)

  function add(values: FeatureValues) {
    addFeature(values.name, values.weight)
    onClose()
  }

  return (
    <Modal title="Добавить признак" open={open} okText="Добавить" cancelText="Отмена" onOk={() => form.submit()} onCancel={onClose} afterClose={() => form.resetFields()}>
      <Form form={form} layout="vertical" initialValues={{ name: '', weight: 0 }} onFinish={add}>
        <Form.Item name="name" label="Название признака" rules={[
          { required: true, whitespace: true, message: 'Укажите название признака.' },
          { max: 120, message: 'Не более 120 символов.' },
          { validator: (_, value: string) => useModelSettingsStore.getState().draft.features.some((feature) => feature.name.toLocaleLowerCase('ru') === value?.trim().toLocaleLowerCase('ru')) ? Promise.reject(new Error('Признак с таким названием уже существует.')) : Promise.resolve() },
        ]}>
          <Input placeholder="Например, неоплаченные транзакции" maxLength={120} />
        </Form.Item>
        <Form.Item name="weight" label="Вес" rules={[{ required: true, type: 'number', min: 0, max: 1, message: 'Укажите вес от 0 до 1.' }]}>
          <InputNumber min={0} max={1} step={0.01} precision={2} controls={false} style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
