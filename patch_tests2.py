import glob
for file in glob.glob('tests/*.py'):
    if file == 'tests/test_config.py':
        continue # skip the one we fully rewrote
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # fix _make_config random_seed
    content = content.replace('{"random_seed": seed, "grid": {"height": rows, "width": cols}}', '{"terrain": {"seed": seed}, "population": {"seed": seed}, "drainage": {"seed": seed}, "grid": {"height": rows, "width": cols}}')
    
    content = content.replace('{"random_seed": 42}', '{"terrain": {"seed": 42}}')
    content = content.replace('{"random_seed": 1}', '{"terrain": {"seed": 1}}')
    content = content.replace('cfg.random_seed', 'cfg.terrain.seed')
    content = content.replace('c.random_seed', 'c.terrain.seed')

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
