import React, { useEffect, useState } from 'react'
import QRCode from 'qrcode'

interface QrCodeProps {
  value: string
  size?: number
  className?: string
}

export const QrCode: React.FC<QrCodeProps> = ({ value, size = 130, className = '' }) => {
  const [dataUrl, setDataUrl] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    QRCode.toDataURL(value, {
      width: size,
      margin: 1,
      color: {
        dark: '#0B1220',
        light: '#FFFFFF',
      },
    })
      .then((url) => {
        if (isMounted) setDataUrl(url)
      })
      .catch((err) => {
        if (isMounted) setError(err.message)
      })

    return () => {
      isMounted = false
    }
  }, [value, size])

  if (error) {
    return (
      <div className="text-[10px] text-block font-mono p-2 border border-block rounded">
        QR generation failed
      </div>
    )
  }

  if (!dataUrl) {
    return (
      <div
        style={{ width: size, height: size }}
        className={`bg-surface2 animate-pulse rounded-lg border border-line ${className}`}
      />
    )
  }

  return (
    <div className={`p-2 bg-white rounded-xl shadow-md border border-line inline-block ${className}`}>
      <img
        src={dataUrl}
        alt={`QR code for ${value}`}
        width={size}
        height={size}
        className="block rounded-lg"
      />
    </div>
  )
}
