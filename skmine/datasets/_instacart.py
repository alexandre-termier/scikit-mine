"""
Base IO for the Instacart dataset
The dataset is available here : `https://www.instacart.com/datasets/grocery-shopping-2017`
"""
import os
import tarfile
import pandas as pd
import numpy as np

try:
    from lxml import html
    LXML_INSTALLED = True
except ImportError: LXML_INSTALLED = False

from .conf import urlopen
from ._base import get_data_home

_IMPORT_MSG = """
lxml is required to install the instacart dataset.
Please run `pip install lxml` before using instacart.
"""

def fetch_instacart(data_home=None):
    """Fetch/load function for the instacart dataset
    Each unique transaction will be represented as a Python list in the resulting pandas Series

    see: https://www.instacart.com/datasets/grocery-shopping-2017

    Parameters
    ----------
    data_home : optional, default: None
        Specify another download and cache folder for the datasets. By default
        all scikit-mine data is stored in `~/scikit_mine_data/` subfolders.

    filename : str
        Name of the file to fetch

    References
    ----------
    .. [1] “The Instacart Online Grocery Shopping Dataset 2017”
            Accessed from https://www.instacart.com/datasets/grocery-shopping-2017

    Notes
    -----
    This returns instacart transactions as a pd.Series, note that you still have access to all
    other data downloaded in your ``data_home`` path

    Returns
    -------
    pd.Series
        Customers orders as a pandas Series
    """
    data_home = data_home or get_data_home()
    data_path = os.path.join(data_home, 'instacart_2017_05_01')
    if not os.path.exists(data_path):
        _download(data_home)
        print("Downloading instacart, this may take a while")

    final_path = os.path.join(data_path, 'instacart.pkl')
    if os.path.exists(final_path):
        s = pd.read_pickle(final_path)
    else:
        orders = _get_orders(data_path)
        s = orders.groupby('order_id')['product_name'].apply(np.unique)
        s.to_pickle(final_path)
    return s

def _get_orders(data_path):
    orders_path = os.path.join(data_path, 'orders_postprocessed.pkl')
    if os.path.exists(orders_path):
        return pd.read_pickle(orders_path)
    order_products_path = os.path.join(data_path, 'order_products__prior.csv')
    products_path = os.path.join(data_path, 'products.csv')
    orders = pd.read_csv(order_products_path, usecols=['order_id', 'product_id'])
    products = pd.read_csv(products_path, usecols=['product_id', 'product_name', 'aisle_id'])
    orders = orders.merge(products, on='product_id', how='inner')
    orders.to_pickle(orders_path)
    return orders

def _download(data_home):
    if not LXML_INSTALLED:
        raise ImportError(_IMPORT_MSG)
    tar_filename = os.path.join(data_home, 'instacart.tar.gz')
    data_link = "https://www.instacart.com/datasets/grocery-shopping-2017"
    tree = html.fromstring(urlopen(data_link).read())
    buttons = tree.xpath("//*[contains(@class, 'ic-btn ic-btn-success ic-btn-lg')]")
    download_link = buttons[0].attrib['href']
    instacart_filedata = urlopen(download_link)
    targz_data = instacart_filedata.read()
    with open(tar_filename, "wb") as f:
        f.write(targz_data)

    tar = tarfile.open(tar_filename, 'r:gz')
    tar.extractall(data_home)
    tar.close()