import { useState, useEffect } from 'react';
import axios from 'axios';
import { QrCode, RotateCcw, Maximize2 } from 'lucide-react';

export default function QRCodePage() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [expiry, setExpiry] = useState<number>(300); // 5 minutes
  const [fullscreen, setFullscreen] = useState(false);
  const [loading, setLoading] = useState(false);

  const generateQRCode = async () => {
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:8000/api/v1/qr/generate', {});
      setQrCode(response.data.qr_code);
      setExpiry(300);
    } catch (error) {
      console.error('Failed to generate QR code:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    generateQRCode();
  }, []);

  useEffect(() => {
    if (expiry <= 0) {
      generateQRCode();
      return;
    }

    const timer = setInterval(() => {
      setExpiry((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [expiry]);

  const minutes = Math.floor(expiry / 60);
  const seconds = expiry % 60;
  const progress = (expiry / 300) * 100;

  if (fullscreen) {
    return (
      <div
        className="fixed inset-0 bg-white flex items-center justify-center z-50 flex-col gap-8"
        onClick={() => setFullscreen(false)}
      >
        {qrCode && (
          <div className="flex flex-col items-center gap-4">
            <img src={qrCode} alt="QR Code" className="w-96 h-96 border-4 border-blue-600 rounded" />
            <div className="text-center">
              <p className="text-4xl font-bold text-gray-800">
                {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
              </p>
              <p className="text-gray-600 text-xl">Expires in</p>
            </div>
          </div>
        )}
        <p className="text-gray-500 text-sm absolute bottom-4">Click anywhere to exit fullscreen</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <QrCode className="w-8 h-8 text-blue-600" />
        <h1 className="text-3xl font-bold">QR Code Attendance</h1>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* QR Display */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Current QR Code</h2>

          {qrCode && (
            <div className="flex flex-col items-center gap-4">
              <img src={qrCode} alt="QR Code" className="w-64 h-64 border-4 border-gray-200 rounded" />

              {/* Countdown Ring */}
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-32 h-32 transform -rotate-90">
                  <circle
                    cx="64"
                    cy="64"
                    r="60"
                    fill="none"
                    stroke="#e0e0e0"
                    strokeWidth="4"
                  />
                  <circle
                    cx="64"
                    cy="64"
                    r="60"
                    fill="none"
                    stroke={progress > 50 ? '#10b981' : progress > 25 ? '#f59e0b' : '#ef4444'}
                    strokeWidth="4"
                    strokeDasharray={`${(progress / 100) * 377} 377`}
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <p className="text-2xl font-bold">
                    {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
                  </p>
                  <p className="text-xs text-gray-500">Expires in</p>
                </div>
              </div>
            </div>
          )}

          <div className="mt-6 space-y-2">
            <button
              onClick={() => generateQRCode()}
              disabled={loading}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <RotateCcw className="w-4 h-4" />
              {loading ? 'Generating...' : 'Refresh QR'}
            </button>

            <button
              onClick={() => setFullscreen(true)}
              className="w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center justify-center gap-2"
            >
              <Maximize2 className="w-4 h-4" />
              Fullscreen (Projector)
            </button>
          </div>
        </div>

        {/* Information */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">How It Works</h2>

          <div className="space-y-4">
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                1
              </div>
              <div>
                <p className="font-semibold">Display QR Code</p>
                <p className="text-sm text-gray-600">Show QR code on projector or device</p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                2
              </div>
              <div>
                <p className="font-semibold">Students Scan</p>
                <p className="text-sm text-gray-600">Students scan with their mobile app</p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                3
              </div>
              <div>
                <p className="font-semibold">Auto Mark</p>
                <p className="text-sm text-gray-600">Attendance marked automatically</p>
              </div>
            </div>

            <div className="mt-6 p-3 bg-yellow-50 border border-yellow-200 rounded">
              <p className="text-sm">
                <span className="font-semibold">Note:</span> QR code expires every 5 minutes. Refresh for a new code.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
