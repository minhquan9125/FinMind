cd D:\finmind\frontend
npm create vite@latest . -- --template react
npm install
npm install tailwindcss axios react-router-dom


Ignore files and continue 
npm install -D tailwindcss @tailwindcss/vite


import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
})





python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn langchain psycopg2-binary

python -m venv venv
venv\Scripts\activate
pip install vnstock scrapling pdfplumber