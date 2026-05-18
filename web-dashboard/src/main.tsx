
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import './firebase'; // Import Firebase initialization

window.addEventListener('unhandledrejection', (event) => {
  const message = event.reason instanceof Error ? event.reason.message : String(event.reason ?? '');
  if (message.includes('A listener indicated an asynchronous response by returning true')) {
    event.preventDefault();
  }
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
