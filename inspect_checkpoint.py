"""
Checkpoint Inspector - Analyze TMRL checkpoint format
"""

import pickle
import sys

def inspect_checkpoint(path):
    """Inspect checkpoint structure"""
    print(f"\n{'='*60}")
    print(f"INSPECTING: {path}")
    print('='*60)
    
    try:
        with open(path, 'rb') as f:
            checkpoint = pickle.load(f)
        
        print(f"\n1. TOP-LEVEL TYPE: {type(checkpoint)}")
        
        # If it's a dict, show keys
        if isinstance(checkpoint, dict):
            print(f"\n2. DICT KEYS: {list(checkpoint.keys())}")
            
            for key in checkpoint.keys():
                value = checkpoint[key]
                print(f"\n   [{key}]")
                print(f"      Type: {type(value)}")
                
                if hasattr(value, '__len__'):
                    try:
                        print(f"      Length: {len(value)}")
                    except:
                        pass
                
                if hasattr(value, 'data'):
                    print(f"      Has .data attribute")
                    data = value.data
                    print(f"      .data type: {type(data)}")
                    if hasattr(data, '__len__'):
                        print(f"      .data length: {len(data)}")
                
                # Show nested structure for dicts
                if isinstance(value, dict):
                    print(f"      Sub-keys: {list(value.keys())[:10]}...")
                
                # Show attributes for objects
                if hasattr(value, '__dict__'):
                    attrs = list(value.__dict__.keys())[:10]
                    print(f"      Attributes: {attrs}")
        
        # If it has attributes, show them
        elif hasattr(checkpoint, '__dict__'):
            print(f"\n2. OBJECT ATTRIBUTES: {list(checkpoint.__dict__.keys())}")
            
            for attr in checkpoint.__dict__.keys():
                value = getattr(checkpoint, attr)
                print(f"\n   [{attr}]")
                print(f"      Type: {type(value)}")
                
                if hasattr(value, '__len__'):
                    try:
                        print(f"      Length: {len(value)}")
                    except:
                        pass
        
        # If it's a list/tuple
        elif isinstance(checkpoint, (list, tuple)):
            print(f"\n2. SEQUENCE LENGTH: {len(checkpoint)}")
            if len(checkpoint) > 0:
                print(f"   First element type: {type(checkpoint[0])}")
                if hasattr(checkpoint[0], '__dict__'):
                    print(f"   First element attrs: {list(checkpoint[0].__dict__.keys())[:10]}")
        
        # Try to find the actual data
        print(f"\n3. SEARCHING FOR DATA...")
        
        # Common TMRL memory locations
        data_locations = []
        
        if isinstance(checkpoint, dict):
            if 'memory' in checkpoint:
                mem = checkpoint['memory']
                if hasattr(mem, 'data'):
                    data_locations.append(('checkpoint["memory"].data', mem.data))
                elif hasattr(mem, '__len__'):
                    data_locations.append(('checkpoint["memory"]', mem))
            
            if 'data' in checkpoint:
                data_locations.append(('checkpoint["data"]', checkpoint['data']))
            
            # TMRL specific
            if 'memory_buffer' in checkpoint:
                data_locations.append(('checkpoint["memory_buffer"]', checkpoint['memory_buffer']))
        
        elif hasattr(checkpoint, 'data'):
            data_locations.append(('checkpoint.data', checkpoint.data))
        
        elif hasattr(checkpoint, 'memory'):
            mem = checkpoint.memory
            if hasattr(mem, 'data'):
                data_locations.append(('checkpoint.memory.data', mem.data))
        
        for location, data in data_locations:
            print(f"\n   FOUND: {location}")
            print(f"   Type: {type(data)}")
            if hasattr(data, '__len__'):
                print(f"   Length: {len(data)}")
            
            # Detect format
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                print(f"   First item type: {type(first)}")
                
                # Check if columnar format
                if hasattr(first, '__len__') and len(first) > 100:
                    print(f"   First item length: {len(first)}")
                    print(f"\n   FORMAT: COLUMNAR (each column = all values for one field)")
                    print(f"   Num columns: {len(data)}")
                    print(f"   Num transitions: {len(first)}")
                    
                    # Show sample values from each column
                    print(f"\n   SAMPLE VALUES (first 3 transitions):")
                    for col_idx, col in enumerate(data[:min(9, len(data))]):
                        try:
                            samples = [col[i] for i in range(min(3, len(col)))]
                            print(f"      Column {col_idx}: {samples}")
                        except:
                            pass
                    
                    # Try to interpret columns
                    print(f"\n   COLUMN INTERPRETATION (guessing):")
                    col_names = ['speed', 'lidar_0', 'lidar_1', 'lidar_2', 
                                'gas', 'brake', 'steering', 'reward', 'done']
                    for i, name in enumerate(col_names[:len(data)]):
                        try:
                            val = data[i][0]
                            print(f"      {i}: {name} = {val}")
                        except:
                            pass
                
                elif isinstance(first, (tuple, list)) and len(first) < 100:
                    print(f"   First item length: {len(first)}")
                    print(f"\n   FORMAT: TUPLE (each item = one transition)")
                    for i, elem in enumerate(first[:5]):
                        print(f"      [{i}] {type(elem)}")
                        if hasattr(elem, 'shape'):
                            print(f"          shape: {elem.shape}")
        
        if not data_locations:
            print("   No standard data locations found")
            print("\n   Trying raw inspection...")
            
            # Deep search
            def find_data(obj, path="root", depth=0):
                if depth > 3:
                    return
                
                if hasattr(obj, 'data') and hasattr(obj.data, '__len__'):
                    print(f"      {path}.data (len={len(obj.data)})")
                
                if isinstance(obj, dict):
                    for k, v in list(obj.items())[:5]:
                        find_data(v, f"{path}['{k}']", depth+1)
                
                elif hasattr(obj, '__dict__'):
                    for k in list(obj.__dict__.keys())[:5]:
                        find_data(getattr(obj, k), f"{path}.{k}", depth+1)
            
            find_data(checkpoint)
        
        print(f"\n{'='*60}")
        print("INSPECTION COMPLETE")
        print('='*60)
        
        return checkpoint
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    paths = [
        "/app/checkpoints/SAC_3container_system_t.tcpt",     # Largest, most likely has data
        "/app/checkpoints/SAC_4_imgs_pretrained_t.tcpt",
        "/app/checkpoints/SAC_LIDAR_docker_trainer_t.tcpt",  # Smallest, might be empty
    ]
    
    for path in paths:
        try:
            import os
            if os.path.exists(path):
                checkpoint = inspect_checkpoint(path)
                
                # If this checkpoint has data, we're done
                if checkpoint is not None:
                    if hasattr(checkpoint, 'memory'):
                        mem = checkpoint.memory
                        
                        # Detect columnar format
                        if hasattr(mem, 'data'):
                            data = mem.data
                            if isinstance(data, list) and len(data) > 0:
                                first_item = data[0]
                                if hasattr(first_item, '__len__') and len(first_item) > 100:
                                    # Columnar format
                                    data_len = len(first_item)
                                else:
                                    data_len = len(data)
                            else:
                                data_len = len(data) if hasattr(data, '__len__') else 0
                        else:
                            data_len = len(mem) if hasattr(mem, '__len__') else 0
                        
                        if data_len > 0:
                            print(f"\n✓ Found checkpoint with {data_len} transitions!")
                            break
                        else:
                            print(f"\n⚠ Checkpoint has 0 transitions, trying next...")
        except Exception as e:
            print(f"Error with {path}: {e}")
            continue