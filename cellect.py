import numpy as np

CELL_DATA_PATH = 'G7_2023.csv'
MODULES = 35
CELLS_PER_MODULE = 12

def read_cells(filename):
    cells = np.genfromtxt(filename, delimiter=',', names=True, dtype=None, encoding=None)
    cells = np.array([(cell['num'], cell['v0'], cell['res_st'], cell['res_lt'] - cell['res_st']) for cell in cells], dtype=[('num', 'i8'), ('v0', 'f8'), ('st', 'f8'), ('lt', 'f8')])
    
    for i, cell in enumerate(cells):
        if cell['num'] in [cell['num'] for cell in cells[:i]]:
            print('Duplicate cell number found:', cell['num'])
            print('This cell must have been tested more than once.')
            print('Decide which result is valid and remove all others.')
            exit(1)
    return cells

def process_cells(cells):
    y = np.array([cell['lt'] for cell in cells])
    x = np.array([cell['v0'] for cell in cells])
    fit = np.polynomial.polynomial.Polynomial.fit(x, y, 1)
    dev_lt = np.abs(cells['lt'] - fit(cells['v0'])) / fit(cells['v0'])
    
    avg_st = np.mean(cells['st'])
    dev_st = np.abs(cells['st'] - avg_st) / avg_st

    largest_dev = np.where(dev_st > dev_lt, 'st', 'lt')
    cells = np.array([(cell['num'], cell['v0'], cell['st'], cell['lt'], dev_st[i], dev_lt[i], max(dev_lt[i], dev_st[i]), largest_dev[i], 0) for i, cell in enumerate(cells)], dtype=[('num', 'i8'), ('v0', 'f8'), ('st', 'f8'), ('lt', 'f8'), ('dev_st', 'f8'), ('dev_lt', 'f8'), ('dev', 'f8'), ('largest_dev', 'U2'), ('mod', 'i8')])
    cells = np.sort(cells, order='dev')

    return cells

cells = read_cells(CELL_DATA_PATH)
cells_sorted = process_cells(cells)

modNum = 1
count = 1
for cell in cells_sorted:
    if count <= 12:
        cell['mod'] = modNum
    else:
        modNum += 1
        count = 1
        cell['mod'] = modNum
    count += 1

good_cells = cells_sorted[ :MODULES * CELLS_PER_MODULE]
bad_cells = cells_sorted[MODULES * CELLS_PER_MODULE: ]

np.savetxt('details.csv', cells_sorted, delimiter=',', header='num,v0,st,lt,dev_st,dev_lt,dev,largest_dev,mod', fmt='%i,%f,%f,%f,%f,%f,%f,%s,%i')

with open ('module_list.txt', 'w') as file:
    for mod in range(1, len(cells_sorted) // CELLS_PER_MODULE):
        file.write(f'Module {mod}: ')
        cells_in_mod = [cell['num'] for cell in cells_sorted if cell['mod'] == mod]
        cells_in_mod.sort()
        file.write(', '.join(str(cell) for cell in cells_in_mod))
        file.write('\n')

with open ('cell_list.txt', 'w') as file:
    cells_sorted.sort(order='num')
    for cell in cells_sorted:
        file.write(f'Cell {cell["num"]}: module {cell["mod"]}\n')