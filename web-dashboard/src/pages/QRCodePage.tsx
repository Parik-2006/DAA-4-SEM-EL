import React, { useState } from 'react';
import { Layout } from '../components';

const QRCodePage: React.FC = () => {
  const [qrData, setQrData] = useState('');
  const [scannedResult, setScannedResult] = useState('');

  const handleQRScan = (data: string) => {
    setScannedResult(data);
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">QR Code Attendance</h1>

        <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
          <div className="bg-gray-100 rounded-lg h-80 flex items-center justify-center">
            <p className="text-gray-600">QR Code Scanner</p>
          </div>

          {scannedResult && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-green-800">
                <strong>Scanned:</strong> {scannedResult}
              </p>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default QRCodePage;
