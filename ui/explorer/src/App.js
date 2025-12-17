import React from 'react';
import Explorer from './Explorer';
import './styles.css';

export default function App() {
  return (
    <div className='app-root'>
      <header className='app-header'>
        <h1>System Code Explorer</h1>
        <p>Transactional TreeSitter-style system navigation</p>
      </header>
      <Explorer />
    </div>
  );
}
