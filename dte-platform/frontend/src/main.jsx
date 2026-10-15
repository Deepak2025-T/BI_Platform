import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import './styles.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <BrowserRouter><App /></BrowserRouter>
)
