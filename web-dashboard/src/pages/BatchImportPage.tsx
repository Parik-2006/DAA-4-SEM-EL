import React, { useState } from 'react';
import { Layout } from '../components';

const BatchImportPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
    }
  };

  const handleImport = async () => {
    if (!file) return;

    setImporting(true);
    try {
      // API call to import
      console.log('Importing file:', file.name);
    } catch (error) {
      console.error('Error importing:', error);
    } finally {
      setImporting(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Batch Import</h1>

        <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <input
              type="file"
              onChange={handleFileSelect}
              accept=".csv,.xlsx"
              className="hidden"
              id="file-input"
            />
            <label
              htmlFor="file-input"
              className="cursor-pointer block text-indigo-600 hover:text-indigo-700"
            >
              <p className="text-lg font-semibold">
                {file ? file.name : 'Click to select file'}
              </p>
              <p className="text-sm text-gray-500">CSV or Excel file</p>
            </label>
          </div>

          <button
            onClick={handleImport}
            disabled={!file || importing}
            className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {importing ? 'Importing...' : 'Import'}
          </button>
        </div>
      </div>
    </Layout>
  );
};

export default BatchImportPage;
