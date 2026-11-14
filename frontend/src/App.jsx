import { useState } from "react";
import UploadPanel from "./components/UploadPanel.jsx";
import SearchPanel from "./components/SearchPanel.jsx";
import ChunkDetailPanel from "./components/ChunkDetailPanel.jsx";
import VocabPanel from "./components/VocabPanel.jsx";

export default function App() {
  const [document, setDocument] = useState(null);

  return (
    <div className="max-w-[820px] mx-auto px-4.5 py-7 pb-16">
      <header className="flex items-center gap-3 mb-5">
        <div className="w-[34px] h-[34px] rounded-[9px] bg-brand flex items-center justify-center text-white font-bold text-[15px] flex-none">
          VR
        </div>
        <div>
          <h1 className="text-[19px] font-semibold m-0">FinMind &mdash; Vector RAG</h1>
          <div className="text-[12.5px] text-muted mt-0.5">
            Chunk + BAAI/bge-m3 embedding + PostgreSQL/pgvector similarity search &mdash; FastAPI backend, React
            frontend (Sections 6.5/9 of the project proposal, configuration B1)
          </div>
        </div>
      </header>

      <UploadPanel onProcessed={setDocument} />

      {document && (
        <>
          <SearchPanel documentId={document.id} />
          <ChunkDetailPanel documentId={document.id} />
          <VocabPanel documentId={document.id} />
        </>
      )}
    </div>
  );
}
