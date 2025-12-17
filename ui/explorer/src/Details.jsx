import React from 'react';

export default function Details({ item }) {
  if (!item) {
    return (
      <div className='details'>
        <p>Select an element to view details</p>
      </div>
    );
  }

  const link = item.file
    ? 'vscode://file/' +
      item.file.replace(/\\\\/g, '/') +
      ':' + (item.line || 1)
    : null;

  return (
    <div className='details'>
      <h3>{item.name}</h3>

      {item.docstring && <pre>{item.docstring}</pre>}

      {item.parameters && (
        <>
          <h4>Parameters</h4>
          <ul>
            {item.parameters.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </>
      )}

      {item.returns && (
        <>
          <h4>Returns</h4>
          <p>{item.returns}</p>
        </>
      )}

      {link && (
        <div className='jump'>
          <a href={link}>Open Definition in VS Code</a>
        </div>
      )}
    </div>
  );
}
