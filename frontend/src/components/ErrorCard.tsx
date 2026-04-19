"use client";

interface Props {
  message: string;
  onReset: () => void;
}

export default function ErrorCard({ message, onReset }: Props) {
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 max-w-md text-center">
        <svg
          className="w-10 h-10 text-red-400 mx-auto mb-3"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
        <p className="text-red-300 text-sm">{message}</p>
      </div>
      <button
        onClick={onReset}
        className="text-gray-400 hover:text-white text-sm transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
