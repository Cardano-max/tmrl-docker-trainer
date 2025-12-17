import React, { useState } from 'react';
import system from './data/system.json';
import Column from './Column';
import Details from './Details';

export default function Explorer() {
  const [stack, setStack] = useState([]);
  const [selected, setSelected] = useState(null);
  const [breadcrumbs, setBreadcrumbs] = useState([]);

  const push = (items, title, level) => {
    setStack(prev => {
      const next = prev.slice(0, level);
      next.push({ title, items });
      return next;
    });

    setBreadcrumbs(prev => {
      const next = prev.slice(0, level);
      next.push(title);
      return next;
    });
  };

  const jumpTo = (level) => {
    setStack(prev => prev.slice(0, level));
    setBreadcrumbs(prev => prev.slice(0, level));
    setSelected(null);
  };

  return (
    <div className='explorer'>
      <div className='columns'>
        <Column
          title='Components'
          items={system.modules}
          onSelect={(m) => {
            push(m.classes || [], m.name, 0);
            setSelected(m);
          }}
        />

        {stack.map((col, idx) => (
          <Column
            key={idx}
            title={col.title}
            items={col.items}
            onSelect={(item) => {
              if (item.methods) {
                push(item.methods, item.name, idx + 1);
              }
              setSelected(item);
            }}
          />
        ))}
      </div>

      <Details
        item={selected}
        breadcrumbs={breadcrumbs}
        onCrumbClick={jumpTo}
      />
    </div>
  );
}
