"""Independent hand-calculated costs and accounting boundaries."""
from decimal import Decimal
import pytest
from src.pricing import calculate_cost


@pytest.mark.parametrize('model,input_count,output_count,read,write,expected',[
    ('gpt-4o-mini',100,20,40,0,'0.000024'),
    ('claude-haiku-4-5-20251001',100,20,40,10,'0.0001665'),
])
def test_cached_input_is_not_charged_twice(model,input_count,output_count,read,write,expected):
    assert calculate_cost(model,input_count,output_count,cache_read_tokens=read,
                          cache_write_tokens=write)==Decimal(expected)


@pytest.mark.parametrize('input_count,output_count,read,write',[
    (-1,1,0,0),(True,1,0,0),(1.5,1,0,0),(1,1,2,0),(1,1,0,1),
])
def test_invalid_accounting_is_rejected(input_count,output_count,read,write):
    with pytest.raises(ValueError):
        calculate_cost('gpt-4o-mini',input_count,output_count,
                       cache_read_tokens=read,cache_write_tokens=write)
