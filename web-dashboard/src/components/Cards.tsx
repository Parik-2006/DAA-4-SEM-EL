import React from 'react';
import { AttendanceRecord } from '@/services/api';
import { Badge } from './UI';
import { Check, Clock, X, FileText } from 'lucide-react';

interface AttendanceRecordCardProps {
  record: AttendanceRecord;
}

const statusConfig = {
  present: {
    icon: <Check size={18} className="text-green-600" />,
    label: 'Present',
    variant: 'success' as const,
    bgColor: 'bg-green-50',
  },
  late: {
    icon: <Clock size={18} className="text-yellow-600" />,
    label: 'Late',
    variant: 'warning' as const,
    bgColor: 'bg-yellow-50',
  },
  absent: {
    icon: <X size={18} className="text-red-600" />,
    label: 'Absent',
    variant: 'danger' as const,
    bgColor: 'bg-red-50',
  },
  excused: {
    icon: <FileText size={18} className="text-blue-600" />,
    label: 'Excused',
    variant: 'info' as const,
    bgColor: 'bg-blue-50',
  },
};

const getRelativeTime = (date: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
};

export const AttendanceRecordCard: React.FC<AttendanceRecordCardProps> = ({
  record,
}) => {
  const config = statusConfig[record.status as keyof typeof statusConfig];
  const markedTime = new Date(record.marked_at);
  const relativeTime = getRelativeTime(markedTime);

  return (
    <div className={`flex items-center gap-4 p-4 rounded-lg border border-gray-100 hover:border-gray-200 hover:shadow-sm transition-all ${config.bgColor}`}>
      {/* Avatar */}
      <div className="flex-shrink-0">
        {record.avatar_url ? (
          <img
            src={record.avatar_url}
            alt={record.student_name}
            className="w-12 h-12 rounded-full object-cover border-2 border-white shadow-sm"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-400 to-purple-600 flex items-center justify-center text-white font-semibold">
            {record.student_name.charAt(0).toUpperCase()}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <h3 className="font-semibold text-gray-900 truncate">
            {record.student_name}
          </h3>
          <span className="text-sm text-gray-500 flex-shrink-0">
            {record.student_id}
          </span>
        </div>
        <p className="text-sm text-gray-600">{record.course_name}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-gray-500">{relativeTime}</span>
          {record.confidence && (
            <span className="text-xs text-gray-500">
              • Confidence: {(record.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>

      {/* Status Badge */}
      <div className="flex-shrink-0 flex items-center gap-2">
        {config.icon}
        <Badge variant={config.variant} size="sm">
          {config.label}
        </Badge>
      </div>
    </div>
  );
};

interface TableColumn<T> {
  key: keyof T;
  label: string;
  render?: (value: any, row: T) => React.ReactNode;
  width?: string;
}

interface TableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  isLoading?: boolean;
  emptyMessage?: string;
}

export function Table<T>({
  data,
  columns,
  isLoading = false,
  emptyMessage = 'No data available',
}: TableProps<T>) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-gray-600">Loading data...</p>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={`px-6 py-3 text-left text-sm font-semibold text-gray-900 ${
                  col.width || ''
                }`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
            >
              {columns.map((col) => (
                <td
                  key={String(col.key)}
                  className={`px-6 py-4 text-sm text-gray-900 ${
                    col.width || ''
                  }`}
                >
                  {col.render ? col.render(row[col.key], row) : String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
