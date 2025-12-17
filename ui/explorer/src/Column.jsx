import React from 'react';

export default function Column({ title, items = [], onSelect }) {
  return (
    <div className='column'>
      <h3>{title}</h3>
      <ul>
        {items.map((item, i) => (
          <li key={i} onClick={() => onSelect(item)}>
            {item.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
