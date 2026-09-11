"use client";

import { create } from "zustand";

type PdfViewerState = {
  isOpen: boolean;
  documentId: string | null;
  fileName: string | null;
  currentPage: number;
  totalPages: number;
  openViewer: (documentId: string, fileName: string, page?: number) => void;
  closeViewer: () => void;
  setCurrentPage: (page: number) => void;
  setTotalPages: (total: number) => void;
};

export const usePdfViewerStore = create<PdfViewerState>((set) => ({
  isOpen: false,
  documentId: null,
  fileName: null,
  currentPage: 1,
  totalPages: 0,
  openViewer: (documentId, fileName, page = 1) =>
    set({
      isOpen: true,
      documentId,
      fileName,
      currentPage: page,
      totalPages: 0,
    }),
  closeViewer: () =>
    set({
      isOpen: false,
      documentId: null,
      fileName: null,
      currentPage: 1,
      totalPages: 0,
    }),
  setCurrentPage: (page) => set({ currentPage: page }),
  setTotalPages: (total) => set({ totalPages: total }),
}));