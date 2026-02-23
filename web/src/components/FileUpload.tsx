import { useRef, useState } from 'react';

interface Props {
  onFile: (file: File) => void;
}

export default function FileUpload({ onFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
        dragging ? 'border-blue-500 bg-blue-950' : 'border-zinc-600 hover:border-zinc-400'
      }`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <p className="text-zinc-300 text-lg">Upload your CV</p>
      <p className="text-zinc-500 text-sm mt-1">Drag and drop or click to browse</p>
      <p className="text-zinc-600 text-xs mt-1">.docx only · max 5 MB</p>
      <input
        ref={inputRef}
        data-testid="cv-file-input"
        type="file"
        accept=".docx"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
      />
    </div>
  );
}
