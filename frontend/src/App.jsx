import React, { useState } from 'react'
import axios from 'axios'
import {
  App as AntApp,
  Card,
  Col,
  Empty,
  Image,
  Layout,
  Row,
  Space,
  Spin,
  Select,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd'
import {
  CloudUploadOutlined,
  MedicineBoxOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'

const { Header, Content } = Layout
const MODEL_NAME = 'MedGemma 1.5 4B IT (Ollama, CPU)'

const ZONE_OPTIONS = [
  { value: 'auto', label: 'Автоопределение (теги DICOM)' },
  { value: 'LUMBAR_SPINE', label: 'Поясничный отдел (L1–L4)' },
  { value: 'HIP_RIGHT', label: 'Тазобедренный сустав — справа' },
  { value: 'HIP_LEFT', label: 'Тазобедренный сустав — слева' },
]

const readError = (err) => {
  const detail = err?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg).join('; ')
  }
  return detail || err?.message || 'Неизвестная ошибка'
}

export default function App() {
  const { message } = AntApp.useApp()
  const [fileList, setFileList] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [anatomy, setAnatomy] = useState('auto')

  const runAnalysis = async (file) => {
    setLoading(true)
    setResult(null)
    const formData = new FormData()
    formData.append('file', file)
    if (anatomy && anatomy !== 'auto') {
      formData.append('zone', anatomy)
    }
    try {
      const { data } = await axios.post('/api/analyze', formData, {
        timeout: 1200000,
      })
      setResult(data)
    } catch (err) {
      message.error(`Анализ не выполнен: ${readError(err)}`)
    } finally {
      setLoading(false)
    }
  }

  const uploadProps = {
    name: 'file',
    multiple: false,
    maxCount: 1,
    accept: '.dcm',
    disabled: loading,
    fileList,
    customRequest: ({ file, onSuccess }) => {
      runAnalysis(file)
      if (onSuccess) onSuccess('ok')
    },
    onChange: ({ fileList: next }) => setFileList(next),
  }

  const verdictTag = () => {
    if (!result) return null
    if (result.decision === 'REJECTED') {
      return (
        <Space>
          <Tag color="error">Ошибка процедуры</Tag>
          <Typography.Text type="secondary">REJECTED</Typography.Text>
        </Space>
      )
    }
    if (result.decision === 'ACCEPTED') {
      return (
        <Space>
          <Tag color="success">Процедура корректна</Tag>
          <Typography.Text type="secondary">ACCEPTED</Typography.Text>
        </Space>
      )
    }
    return <Tag color="warning">Оценка не распознана</Tag>
  }

  const renderResponse = (text) =>
    text.split(/(\bACCEPTED\b|\bREJECTED\b)/g).map((part, index) => {
      if (/^\bACCEPTED\b$/.test(part)) {
        return (
          <Tag key={index} color="success">
            ACCEPTED
          </Tag>
        )
      }
      if (/^\bREJECTED\b$/.test(part)) {
        return (
          <Tag key={index} color="error">
            REJECTED
          </Tag>
        )
      }
      return <span key={index}>{part}</span>
    })

  const meta = result?.metadata || {}
  const zoneCell = (
    <Space size={4} wrap>
      <span>{result?.zone_label || '—'}</span>
    </Space>
  )
  const metaRows = [
    { key: '1', param: 'Производитель денситометра', value: meta.manufacturer || '—' },
    { key: '2', param: 'Модель', value: meta.model || '—' },
    { key: '3', param: 'BodyPartExamined', value: meta.body_part || '—' },
    { key: '4', param: 'Зона (распознана)', value: zoneCell },
    { key: '5', param: 'Modality', value: meta.modality || '—' },
    { key: '6', param: 'Вид сканирования', value: meta.view_position || '—' },
    { key: '7', param: 'Протокол / Исследование', value: meta.protocol_name || meta.study_description || '—' },
    { key: '8', param: 'Разрешение снимка', value: meta.resolution || '—' },
  ]
  const columns = [
    {
      title: 'Параметр',
      dataIndex: 'param',
      width: '45%',
      render: (value) => (
        <Typography.Text strong style={{ fontSize: 12 }}>
          {value}
        </Typography.Text>
      ),
    },
    {
      title: 'Значение',
      dataIndex: 'value',
      render: (value) => <Typography.Text style={{ fontSize: 12 }}>{value}</Typography.Text>,
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Spin fullscreen spinning={loading} tip="MedGemma 1.5 проверяет корректность укладки и разметки DXA..." />
      <Header
        style={{
          background: '#001529',
          paddingInline: 24,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <Space size={16} align="center">
          <SafetyCertificateOutlined style={{ color: '#13c2c2', fontSize: 28 }} />
          <Typography.Title level={4} style={{ margin: 0, color: '#ffffff' }}>
            Система контроля качества денситометрии
          </Typography.Title>
        </Space>

      </Header>

      <Content style={{ padding: 24 }}>
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Card variant="borderless" style={{ boxShadow: '0 1px 2px rgba(0,0,0,0.08)' }}>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Upload.Dragger {...uploadProps}>
                  <p>
                    <CloudUploadOutlined style={{ fontSize: 44, color: '#0b6b6b' }} />
                  </p>
                  <Typography.Title level={5} style={{ marginTop: 8, marginBottom: 4 }}>
                    Нажмите или перетащите DICOM-файл снимка (.dcm)
                  </Typography.Title>
                </Upload.Dragger>
                <Space size={8}>
                  <span>Анатомическая область:</span>
                  <Select
                    value={anatomy}
                    onChange={setAnatomy}
                    disabled={loading}
                    options={ZONE_OPTIONS}
                    style={{ width: 360 }}
                  />
                </Space>
              </Space>
            </Card>
          </Col>

          <Col xs={24} xl={14}>
            <Card
              title={
                <Space align="center">
                  <MedicineBoxOutlined style={{ color: '#0b6b6b' }} />
                  <span>Технический аудит снимка</span>
                </Space>
              }
              extra={verdictTag()}
              style={{ height: '100%', boxShadow: '0 1px 2px rgba(0,0,0,0.08)' }}
            >
              {!result ? (
                <Empty
                  description="Загрузите DICOM-файл для запуска аудита укладки и ROI-разметки"
                  style={{ paddingTop: 48 }}
                />
              ) : (
                <>
                  <Typography.Paragraph
                    style={{
                      whiteSpace: 'pre-wrap',
                      margin: 0,
                      fontSize: 14,
                      lineHeight: 1.7,
                    }}
                  >
                    {renderResponse(result.response)}
                  </Typography.Paragraph>
                </>
              )}
            </Card>
          </Col>

          <Col xs={24} xl={10}>
            <Card
              title="Данные аппарата"
              style={{ height: '100%', boxShadow: '0 1px 2px rgba(0,0,0,0.08)' }}
            >
              {!result ? (
                <Empty description="Технические метаданные появятся после анализа" style={{ paddingTop: 48 }} />
              ) : (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <Table
                    size="small"
                    bordered
                    pagination={false}
                    rowKey="key"
                    columns={columns}
                    dataSource={metaRows}
                  />
                  {result.preview_base64 && (
                    <div style={{ textAlign: 'center' }}>
                      <Image
                        src={`data:image/png;base64,${result.preview_base64}`}
                        alt="DXA preview"
                        width="100%"
                        style={{ borderRadius: 8 }}
                      />
                    </div>
                  )}
                </Space>
              )}
            </Card>
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}