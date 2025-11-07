import numpy as np
import matplotlib.pyplot as plt

CELL_DATA_PATH = 'G7_2023.csv'
CELLS_PER_MODULE = 12

def read_cells(filename):
    cells = np.genfromtxt(fname=filename, delimiter=',', names=True, dtype=None)
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

    # remove cells with dev_st > 1/2 standard deviation
    std_dev_st = np.std(dev_st)
    st_mean = np.mean(dev_st)
    bad_cells = cells[dev_st >= st_mean + 0.5 * std_dev_st]
    cells = cells[dev_st < st_mean + 0.5 * std_dev_st]

    dev_st = np.abs(cells['st'] - avg_st) / avg_st
    dev_lt = np.abs(cells['lt'] - fit(cells['v0'])) / fit(cells['v0'])
    largest_dev = np.where(dev_st > dev_lt, 'st', 'lt')

    bc_dev_st = np.abs(bad_cells['st'] - avg_st) / avg_st
    bc_dev_lt = np.abs(bad_cells['lt'] - fit(bad_cells['v0'])) / fit(bad_cells['v0'])
    bc_largest_dev = np.where(bc_dev_st > bc_dev_lt, 'st', 'lt')

    median_lt = np.median(cells['lt'])
    cells = np.array([(cell['num'], cell['v0'], cell['st'], cell['lt'], dev_st[i], dev_lt[i], max(dev_lt[i], dev_st[i]), largest_dev[i], cell['lt'] - median_lt, abs(cell['lt'] - median_lt), 0) for i, cell in enumerate(cells)], dtype=[('num', 'i8'), ('v0', 'f8'), ('st', 'f8'), ('lt', 'f8'), ('dev_st', 'f8'), ('dev_lt', 'f8'), ('dev', 'f8'), ('largest_dev', 'U2'), ('dist', 'f8'), ('abs_dist', 'f8'), ('mod', 'i8')])
    bad_cells = np.array([(cell['num'], cell['v0'], cell['st'], cell['lt'], bc_dev_st[i], bc_dev_lt[i], max(bc_dev_lt[i], bc_dev_st[i]), bc_largest_dev[i], cell['lt'] - median_lt, abs(cell['lt'] - median_lt), 0) for i, cell in enumerate(bad_cells)], dtype=[('num', 'i8'), ('v0', 'f8'), ('st', 'f8'), ('lt', 'f8'), ('dev_st', 'f8'), ('dev_lt', 'f8'), ('dev', 'f8'), ('largest_dev', 'U2'), ('dist', 'f8'), ('abs_dist', 'f8'), ('mod', 'i8')])
    
    cells = np.sort(cells, order='abs_dist')
    
    while (len(cells) % CELLS_PER_MODULE > 0):
        bad_cells = np.concatenate((bad_cells, [cells[-1]]))
        cells = np.delete(cells, -1)
    
    print('Number of cells excluded:', len(bad_cells))
    print('Number of cells remaining:', len(cells))

    # plot the distribution of dev_st
    plt.hist(dev_st, bins=40)
    plt.xlabel('Deviation from mean')
    plt.ylabel('Number of cells')
    plt.tight_layout()
    plt.savefig('dev_st distribution')
    plt.clf()

    return cells, bad_cells

def assign_to_modules(cells, starting_module=1):
    cells = np.sort(cells, order='dist')
    total = len(cells)

    # find the index of the cell with dist closest to 0
    median_index = np.argmin(np.abs(cells['dist']))
    
    # adjust the center to be a multiple of CELLS_PER_MODULE so we can match as many cells as possible
    dist_start_to_middle = median_index - CELLS_PER_MODULE // 2
    dist_middle_to_end = total - median_index + CELLS_PER_MODULE // 2
    remaining_end = (total - dist_middle_to_end) % CELLS_PER_MODULE
    remaining_start = dist_start_to_middle % CELLS_PER_MODULE
    if remaining_start <= remaining_end:
        center = median_index - remaining_start
    else:
        center = median_index + remaining_end

    mod = 1
    lower = center - CELLS_PER_MODULE // 2
    upper = center + CELLS_PER_MODULE // 2
    up_or_down = 1
    while lower >= 0 and upper <= total:
        cells[lower:upper]['mod'] = starting_module + mod - 1
        center += mod * up_or_down * CELLS_PER_MODULE
        lower = center - CELLS_PER_MODULE // 2
        upper = center + CELLS_PER_MODULE // 2
        mod += 1
        up_or_down *= -1

    center += mod * up_or_down * CELLS_PER_MODULE

    if lower < 0:
        center += mod * up_or_down * CELLS_PER_MODULE
        lower = center - CELLS_PER_MODULE // 2
        upper = center + CELLS_PER_MODULE // 2
        while upper <= total:
            cells[lower:upper]['mod'] = starting_module + mod - 1
            center += CELLS_PER_MODULE
            lower = center - CELLS_PER_MODULE // 2
            upper = center + CELLS_PER_MODULE // 2
            mod += 1
    elif upper > total:
        upper = center + CELLS_PER_MODULE // 2
        lower = center - CELLS_PER_MODULE // 2
        while lower >= 0:
            cells[lower:upper]['mod'] = starting_module + mod - 1
            center -= CELLS_PER_MODULE
            lower = center - CELLS_PER_MODULE // 2
            upper = center + CELLS_PER_MODULE // 2
            mod += 1

    total_modules = mod - 1
            
    return cells, total_modules

cells = read_cells(CELL_DATA_PATH)
cells, bad_cells = process_cells(cells)
cells, total_modules = assign_to_modules(cells, 1)

# find cells that are not assigned to any module
unused = cells[cells['mod'] == 0]
cells = cells[cells['mod'] != 0]

# add the bad cells to the unused list
unused = np.concatenate((unused, bad_cells))
unused = np.sort(unused, order='dist')
unused = assign_to_modules(unused, total_modules + 1)[0]

cells_sorted = np.concatenate((cells, unused))

plt.scatter(cells_sorted['mod'], cells_sorted['dist'])
plt.xlabel('Module')
plt.ylabel('Distance from median')
plt.tight_layout()
plt.savefig('deviations by module')

np.savetxt('useless_details--NOT_important--DO_NOT_READ.csv', cells_sorted, delimiter=',', header='num,v0,st,lt,dev_st,dev_lt,dev,largest_dev,dist,abs_dist,mod', fmt='%i,%f,%f,%f,%f,%f,%f,%s,%f,%f,%i')

with open ('module_list.txt', 'w') as file:
    for mod in range(1, len(cells_sorted) // CELLS_PER_MODULE + 1):
        file.write(f'Module {mod}: ')
        cells_in_mod = [cell['num'] for cell in cells_sorted if cell['mod'] == mod]
        cells_in_mod.sort()
        file.write(', '.join(str(cell) for cell in cells_in_mod))
        file.write('\n')
    leftovers = [cell['num'] for cell in cells_sorted if cell['mod'] == 0]
    if len(leftovers) > 0:
        leftovers.sort()
        file.write('Leftovers: ')
        file.write(', '.join(str(cell) for cell in leftovers))

with open ('cell_list.txt', 'w') as file:
    cells_sorted.sort(order='num')
    for cell in cells_sorted:
        file.write(f'Cell {cell["num"]}: module {cell["mod"] if cell["mod"] != 0 else 'NONE'}\n')
