res_st = 0.00001
res_lt = 0.001
rank_st = 120
rank_lt = 100
cells_tested = 123

print(f'Resistance: {res_st:.3e}         {res_lt:.3e}')
print(f'Rank:       {rank_st} of {cells_tested}        {rank_lt} of {cells_tested}')
print(f'Percentile: {rank_st / cells_tested * 100:.0f}%               {rank_lt / cells_tested * 100:.0f}%')