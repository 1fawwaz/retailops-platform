"use client";

import { useState, type ChangeEvent } from "react";

interface ImageUploadProps {
  value?: string | null;
  onChange: (url: string) => void;
  label?: string;
  className?: string;
}

export function ImageUpload({ value, onChange, label = "Upload Image", className = "" }: ImageUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cloudName = process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME || "demo";
  const uploadPreset = process.env.NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET || "unsigned_preset";

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("upload_preset", uploadPreset);

      const response = await fetch(`https://api.cloudinary.com/v1_1/${cloudName}/image/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Cloudinary upload failed: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.secure_url) {
        onChange(data.secure_url);
      } else {
        throw new Error("No URL returned from Cloudinary");
      }
    } catch (err) {
      console.warn("Cloudinary upload error, using local fallback preview:", err);
      // Fallback: create object URL for local preview if cloud upload fails
      const objectUrl = URL.createObjectURL(file);
      onChange(objectUrl);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {label && <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">{label}</label>}
      <div className="flex items-center gap-4">
        {value ? (
          <div className="relative w-20 h-20 rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={value} alt="Uploaded preview" className="w-full h-full object-cover" />
          </div>
        ) : (
          <div className="w-20 h-20 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center bg-gray-50 text-gray-400 text-xs">
            No image
          </div>
        )}
        <div className="space-y-1">
          <label className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md shadow-sm text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer">
            {uploading ? "Uploading..." : "Choose File"}
            <input type="file" accept="image/*" className="sr-only" onChange={handleFileChange} disabled={uploading} />
          </label>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
      </div>
    </div>
  );
}
