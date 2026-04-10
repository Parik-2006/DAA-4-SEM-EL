import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick }) => (
  <div
    onClick={onClick}
    className={`
      bg-white rounded-xl shadow-sm border border-gray-100 
      p-6 transition-all duration-200 hover:shadow-md hover:border-gray-200
      ${onClick ? 'cursor-pointer' : ''}
      ${className}
    `}
  >
    {children}
  </div>
);

interface StatCardProps {
  label: string;
  value: string | number;
  color: 'primary' | 'success' | 'warning' | 'danger' | 'info';
  icon?: React.ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

const colorMap = {
  primary: 'bg-indigo-50 text-indigo-600 border-indigo-200',
  success: 'bg-green-50 text-green-600 border-green-200',
  warning: 'bg-yellow-50 text-yellow-600 border-yellow-200',
  danger: 'bg-red-50 text-red-600 border-red-200',
  info: 'bg-blue-50 text-blue-600 border-blue-200',
};

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  color,
  icon,
  trend,
}) => (
  <Card className={`border ${colorMap[color]}`}>
    <div className="flex justify-between items-start">
      <div className="flex-1">
        <p className="text-sm font-medium text-gray-600 mb-2">{label}</p>
        <div className="flex items-baseline gap-2">
          <p className={`text-3xl font-bold ${colorMap[color].split(' ')[1]}`}>
            {value}
          </p>
          {trend && (
            <span
              className={`text-xs font-semibold ${
                trend.isPositive ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </span>
          )}
        </div>
      </div>
      {icon && (
        <div className={`p-3 rounded-lg ${colorMap[color].split(' ')[0]}`}>
          {icon}
        </div>
      )}
    </div>
  </Card>
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  children: React.ReactNode;
}

const variantMap = {
  primary: 'bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-400',
  secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 disabled:bg-gray-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-400',
  ghost: 'text-gray-700 hover:bg-gray-100 disabled:text-gray-400',
};

const sizeMap = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled,
  children,
  ...props
}) => (
  <button
    disabled={disabled || isLoading}
    className={`
      font-semibold rounded-lg transition-all duration-200
      flex items-center justify-center gap-2
      ${variantMap[variant]}
      ${sizeMap[size]}
      disabled:cursor-not-allowed
      ${isLoading ? 'opacity-70' : ''}
    `}
    {...props}
  >
    {isLoading && (
      <svg
        className="animate-spin h-4 w-4"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    )}
    {children}
  </button>
);

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'gray';
  size?: 'sm' | 'md';
}

const badgeColorMap = {
  primary: 'bg-indigo-100 text-indigo-700',
  success: 'bg-green-100 text-green-700',
  warning: 'bg-yellow-100 text-yellow-700',
  danger: 'bg-red-100 text-red-700',
  info: 'bg-blue-100 text-blue-700',
  gray: 'bg-gray-100 text-gray-700',
};

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'primary',
  size = 'md',
}) => (
  <span
    className={`
      font-semibold rounded-full ${badgeColorMap[variant]}
      ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'}
    `}
  >
    {children}
  </span>
);
