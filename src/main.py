#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import os
import pandas as pd
from gooey import Gooey, GooeyParser
from bs4 import BeautifulSoup
from datetime import date
from itertools import chain


class ResultsOverview():
    links = []
    
    def make_soup(self, base):
        req = requests.get(base)
        soup = BeautifulSoup(req.content, 'html.parser')
        return soup

    def get_links(self, soup, query = '/properties/'):
        links = []
        rm_url = 'https://www.rightmove.co.uk'
        for i in soup.find_all('a', href = True):
            if query in i['href']:
                links.append(rm_url+i['href'])
        links = list(set(links))
        return links                
    
    def count_links(self, soup, query = '/properties/'):
        links = self.get_links(soup, query)
        return(len(links))
    
    def get_all_links(self, base, query = '/properties/'):
        page1 = self.make_soup(base)
        n_res = self.count_links(page1, query)
        if(n_res < 24):
            return self.get_links(page1, query)
        else:
            all_links = self.get_links(page1, query)
            page_counter = 1
            while(n_res >= 24):
                index_counter = page_counter*24
                page_url = f"{base}&index={index_counter}"
                cur_page = self.make_soup(page_url)
                cur_res = self.get_links(cur_page, query)
                all_links.extend(cur_res)
                n_res = len(cur_res)
                page_counter += 1
                
            all_links = list(set(all_links))
            return(all_links)
        
    def __init__(self, base_url):
        self.links = self.get_all_links(base_url)

class ResultsScraper():
    results = {}
    data = None
    
    def make_soup(self, base):
        req = requests.get(base)
        soup = BeautifulSoup(req.content, 'html.parser')
        return soup
    
    def _clean_date(self, cdate):
        cdate = re.sub('<.*?>', '', str(cdate))
        if cdate == 'Now': 
            return date.today().strftime("%d/%m/%Y")
        if(re.match('.*/.*/.*', cdate)):
            return cdate
        else:
            return "NaN"
        
    def _get_date(self, soup):
        details = soup.find('dl')
        cdate = details.find('dd')
        cdate = self._clean_date(cdate)
        return cdate
            
    def _clean_price(self, price):
        price = re.sub('<.*?>', '', str(price))
        price = re.sub('£|,| |pcm','',str(price))
        return price
    
    def _get_price(self, soup):
        spans = soup.find_all('span')
        price = 'N/A'
        for i in list(spans):
            if ' pcm' in str(i):
                price = self._clean_price(i)
                break
        return price
          
    def _clean_location(self, location):
        location_str = re.sub('<.*?>', '', str(location))
        
        if re.search(', ', location_str):
            quarter = location_str.split(", ")
        elif re.search(',', location_str):
             quarter = location_str.split(", ")
        else: quarter = []
             
        if len(quarter) == 4:
                quarter = quarter[1]
        elif len(quarter) == 3:
                quarter = quarter[0]
        else: quarter = "N/A"
        return quarter
        
    def _get_location(self, soup):
        h2s = soup.find_all("h2")
        quarter = ""
        for i in list(h2s):
            if 'mapTitleScrollAnchor' in str(i):
                quarter = self._clean_location(i)
                break
        return quarter
                
    def scrape_url(self, url):
        soup = self.make_soup(url)
        
        cdate = self._get_date(soup)
        price = self._get_price(soup)
        location = self._get_location(soup)
        
        return price, cdate, location
    
    def _format_times(self, column, sort_by = True):
        self.data[column] = pd.to_datetime(self.data[column],
                                                     format="%d/%m/%Y")
        if sort_by is True:
            self._sort_times(column)
            
        self.data[column] = self.data[column].dt.strftime("%d/%m/%Y")
    
    def _sort_times(self, column):
        self.data.sort_values(by=[column],ascending=False,inplace=True)
    
    def __init__(self, urls):
        results = self.results
        for i in urls:
            print(i)
            results[i] = self.scrape_url(i)
        self.data = pd.DataFrame.from_dict(results,orient='index')
        self.data.reset_index(level=0, inplace=True)
        self.data.columns = ['URL','Price', 'Available from', 'Location']
        self.data["Date added to database"] = date.today().strftime("%d/%m/%Y")
        
        self._format_times('Available from')
        self._format_times('Date added to database', sort_by = False)
        
        

class CombinedResults:
    res = None
    
    def _format_times(self, column, sort_by = True):
        self.res[column] = pd.to_datetime(self.res[column],
                                                     format="%d/%m/%Y")
        if sort_by is True:
            self._sort_times(column)
            
        self.res[column] = self.res[column].dt.strftime("%d/%m/%Y")
    
    def _sort_times(self, column):
        self.res.sort_values(by=[column],ascending=False,inplace=True)
    
    def __init__(self, base, path_to_existing=None):
        
        # check if only one link has been passed, force list in that case
        if base.__class__ is not list:
            base = list(base)
         
        # loop over base links and create overview links
        links = [ResultsOverview(lin).links for lin in base]
        # keep only unique links and un-nest list
        links = list(set(chain.from_iterable(links))) 
        
        # check if some older output data exists
        if (path_to_existing is None 
            or not os.path.isfile(path_to_existing)
            or os.path.getsize(path_to_existing) == 0): 
            res = ResultsScraper(links)
            self.res = res.data
        else:
            ex = pd.read_csv(path_to_existing, sep='\t')
            
            # remove offers no longer present on the site
            ex = ex.query('URL in @links')
            
            links = [i for i in links if i not in ex.iloc[:,0].values]
            if len(links) > 0:
                res = ResultsScraper(links)
                
            else:
                print("No new offers detected. Will quit without update.")
                exit(0)
            
            out = ex.append(res.data, ignore_index = True)
            self.res = out
        
        self._format_times('Available from')
        self._format_times('Date added to database', sort_by = False)
        
        
        
    def write_out(self, out_path, overwrite=True):
        if os.path.exists(out_path) and overwrite is not True:
            raise FileExistsError(f"{out_path} exists and overwrite=False")
        else:
            self.res.to_csv(out_path, sep='\t',index=False)
          
@Gooey(advanced=True,
       auto_start=False,
       program_name='Rightmove Scraper',
       default_size=(1300,700), 
       required_cols = 1)
def main():
    parser = GooeyParser()
    parser.add_argument("url",  widget = "TextField", help = "Your search URL. See the manual for details.")
    parser.add_argument("outfile", widget = "FileSaver", help="File to store the results in.")
    args = parser.parse_args()
    links = [args.url]
    out = args.outfile
    cr = CombinedResults(links, out)
    cr.write_out(out, overwrite=True)
    

if __name__ == '__main__':
    main()
# base = "https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=REGION%5E{CODE}&minBedrooms=2&maxPrice=1200&minPrice=500&propertyTypes=&maxDaysSinceAdded=14&includeLetAgreed=false&mustHave=&dontShow=retirement%2ChouseShare&furnishTypes=&letType=longTerm&keywords="
# https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=REGION%5E93598&minBedrooms=2&maxPrice=1200&minPrice=500&propertyTypes=&maxDaysSinceAdded=14&includeLetAgreed=false&mustHave=&dontShow=retirement%2ChouseShare&furnishTypes=&letType=longTerm&keywords=
# regions = [93598,66970,66978]
# links = [base.format(CODE=i) for i in regions]

# out = '/home/jesko/projects/rightmove_scaper/scrape_results.tsv'

# cr = CombinedResults(links,path_to_existing=out)
# cr.write_out(out, overwrite=True)
