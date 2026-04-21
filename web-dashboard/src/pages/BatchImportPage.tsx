import { useState } from 'react';
import axios from 'axios';
import { Upload, AlertCircle, CheckCircle2, Trash2 } from 'lucide-react';

interface ImportRow {
  name: string;
  email: string;
  student_id: string;
  course_id: string;
  status: 'pending' | 'valid' | 'invalid';
  error?: string;
}

export default function BatchImportPage() {
  const [step, setStep] = useState<'upload' | 'preview' | 'result'>(
    'upload'
  );
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [fileName, setFileName] = useState('');

  const downloadTemplate = () => {
    const csv = 'name,email,student_id,course_id\nJohn Doe,john@example.com,STU001,COURSE001\n';
    const element = document.createElement('a');
    element.setAttribute(
      'href',
      'data:text/csv;charset=utf-8,' + encodeURIComponent(csv)
    );
    element.setAttribute('download', 'student_template.csv');
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const csv = event.target?.result as string;
      const lines = csv.split('\n').slice(1); // Skip header
      const parsed: ImportRow[] = lines
        .filter((line) => line.trim())
        .map((line) => {
          const [name, email, student_id, course_id] = line.split(',');
          const errors = [];

          if (!name?.trim()) errors.push('Name required');
          if (!email?.includes('@')) errors.push('Invalid email');
          if (!student_id?.trim()) errors.push('Student ID required');
          if (!course_id?.trim()) errors.push('Course ID required');

          return {
            name: name?.trim() || '',
            email: email?.trim() || '',
            student_id: student_id?.trim() || '',
            course_id: course_id?.trim() || '',
            status: errors.length === 0 ? 'valid' : 'invalid',
            error: errors.length > 0 ? errors.join('; ') : undefined,
          };
        });

      setRows(parsed);
      setStep('preview');
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    const validRows = rows.filter((r) => r.status === 'valid');

    if (validRows.length === 0) {
      alert('No valid rows to import');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(
        'http://localhost:8000/api/v1/admin/batch-import',
        { students: validRows }
      );

      setResults({
        success: response.data.success_count,
        failed: response.data.failed_count,
        total: validRows.length,
      });
      setStep('result');
    } catch (error: any) {
      alert(`Import failed: ${error.response?.data?.detail}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Upload className="w-8 h-8 text-blue-600" />
        <h1 className="text-3xl font-bold">Batch Student Import</h1>
      </div>

      {step === 'upload' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="border-2 border-dashed border-blue-300 rounded-lg p-8 text-center">
            <Upload className="w-12 h-12 mx-auto mb-4 text-blue-600" />
            <p className="text-lg font-semibold mb-2">Upload CSV File</p>
            <p className="text-gray-600 mb-4">
              Select a CSV file with student data (name, email, student_id, course_id)
            </p>

            <input
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="hidden"
              id="csv-upload"
            />
            <label
              htmlFor="csv-upload"
              className="inline-block px-6 py-2 bg-blue-600 text-white rounded cursor-pointer hover:bg-blue-700"
            >
              Choose File
            </label>

            <div className="mt-6 pt-6 border-t">
              <button
                onClick={downloadTemplate}
                className="px-4 py-2 text-blue-600 hover:text-blue-700 font-semibold"
              >
                📥 Download Template
              </button>
            </div>
          </div>
        </div>
      )}

      {step === 'preview' && (
        <div className="space-y-4">
          <div className="bg-blue-50 p-4 rounded flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600" />
            <span className="text-sm">
              Showing {rows.length} rows from {fileName}
            </span>
          </div>

          <div className="bg-white rounded-lg shadow overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-2 text-left">Name</th>
                  <th className="px-4 py-2 text-left">Email</th>
                  <th className="px-4 py-2 text-left">Student ID</th>
                  <th className="px-4 py-2 text-left">Course ID</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Error</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-2">{row.name}</td>
                    <td className="px-4 py-2">{row.email}</td>
                    <td className="px-4 py-2">{row.student_id}</td>
                    <td className="px-4 py-2">{row.course_id}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          row.status === 'valid'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-red-600 text-xs">{row.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex gap-4">
            <button
              onClick={() => setStep('upload')}
              className="px-6 py-2 border border-gray-300 rounded hover:bg-gray-50"
            >
              Back
            </button>
            <button
              onClick={handleImport}
              disabled={loading || !rows.some((r) => r.status === 'valid')}
              className="px-6 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? 'Importing...' : `Import ${rows.filter((r) => r.status === 'valid').length} Valid Rows`}
            </button>
          </div>
        </div>
      )}

      {step === 'result' && results && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <CheckCircle2 className="w-16 h-16 mx-auto text-green-600 mb-4" />
          <h2 className="text-2xl font-bold mb-4">Import Complete</h2>

          <div className="grid md:grid-cols-3 gap-4 mb-6">
            <div className="p-4 bg-green-50 rounded">
              <p className="text-3xl font-bold text-green-600">{results.success}</p>
              <p className="text-sm text-gray-600">Successful</p>
            </div>
            <div className="p-4 bg-red-50 rounded">
              <p className="text-3xl font-bold text-red-600">{results.failed}</p>
              <p className="text-sm text-gray-600">Failed</p>
            </div>
            <div className="p-4 bg-blue-50 rounded">
              <p className="text-3xl font-bold text-blue-600">{results.total}</p>
              <p className="text-sm text-gray-600">Total Processed</p>
            </div>
          </div>

          <button
            onClick={() => {
              setStep('upload');
              setRows([]);
              setResults(null);
            }}
            className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Import Another File
          </button>
        </div>
      )}
    </div>
  );
}
