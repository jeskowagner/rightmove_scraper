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
    """ResultsOverview is a class that extracts rightmove ads from the results
    overview page. It opens the webpage, detects all links to offers and saves
    them to the links slot.
    
    Usage:
        overview = ResultsOverview("https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=REGION%5E93598")
        offers = overview.links
    """
    
    links = []
    
    def make_soup(self, base):
        req = requests.get(base)
        soup = BeautifulSoup(req.content, "html.parser")
        return soup

    def get_links(self, soup, query = "/properties/"):
        links = []
        rm_url = "https://www.rightmove.co.uk"
        for i in soup.find_all("a", href = True):
            if query in i["href"]:
                links.append(rm_url+i["href"])
        links = list(set(links))
        return links                
    
    def count_links(self, soup, query = "/properties/"):
        links = self.get_links(soup, query)
        return(len(links))
    
    def get_all_links(self, base, query = "/properties/"):
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
    """ResultsScraper scrapes all information from a rightmove rental offer
    and saves the data in a Dataframe row to the data slot.
    
    Note: if rightmove detects a huge load of requests coming from your IP
    they may block further accesses. I have not encountered this yet, but it
    has been described elsewhere. Requests for ~100 links typically do not run
    into this issue, so check how many links you are trying to scrape.
    
    Usage:
        res = ResultsScraper(offer_url)
        dat = res.get_df()
    """
    results = {}
    data = None
    
    # for future reference, these are the html class ids     
    # patterns = {}
    # patterns["price"] = ("div","_1gfnqJ3Vtd1z40MlC0MzXu")
    # patterns["date_added"] = ("div","_2nk2x6QhNB1UrxdI5KpvaF")
    # patterns["let_term"] = ("div", "_2RnXSVJcWbWv4IpBC1Sng6")
    # patterns["furnished"] = ("div", "_2RnXSVJcWbWv4IpBC1Sng6")
    # patterns["property_type"] = ("div", "_1fcftXUEbWfJOJzIUeIHKt")
    # patterns["bedrooms"] = ("div", "_1fcftXUEbWfJOJzIUeIHKt")
    # patterns["location"] = ("h2", "gBaD1fLdPaNTbHErZvX7y")
    # patterns["agency"] = ("h3", "_3PpywCmRYxC0B-ShNWxstv")
    
    def _make_soup(self, base):
        req = requests.get(base)
        soup = BeautifulSoup(req.content, "html.parser")
        return soup
    
    def _scrub_html_field(self, html):
        return re.sub("<.*?>", '', str(html)) # delete all in triangle brackets
    
    # the following functions extract specific html fields and scrub data as needed
    def _get_date_added(self, soup):
        date = soup.find("div",class_="_2nk2x6QhNB1UrxdI5KpvaF")
        return self._clean_date(date)
    
    def _get_agency(self, soup):
        agency = soup.find("h3", class_="_3PpywCmRYxC0B-ShNWxstv")
        return self._scrub_html_field(agency)
    
    def _get_bedrooms(self, soup):
        bedrooms = soup.find_all("div",class_="_1fcftXUEbWfJOJzIUeIHKt")[1]
        return self._scrub_html_field(bedrooms)
    
    def _get_type(self, soup):
        flat_type = soup.find("div",class_="_1fcftXUEbWfJOJzIUeIHKt")
        return self._scrub_html_field(flat_type)
    
    def _get_furnished(self, soup):
        furnished = soup.find_all("div",class_="_2RnXSVJcWbWv4IpBC1Sng6")[1]
        return self._scrub_html_field(furnished)
    
    def _get_term(self, soup):
        term = soup.find("div",class_="_2RnXSVJcWbWv4IpBC1Sng6")
        return self._scrub_html_field(term)
    
    def _get_date_let(self, soup):
        details = soup.find("dl")
        cdate = details.find("dd")
        return self._clean_date(cdate)
            
    def _get_price(self, soup):
        span = soup.find("div",class_="_1gfnqJ3Vtd1z40MlC0MzXu").find("span")
        price = self._scrub_html_field(span)
        price = re.sub("£|,| |pcm",'',str(price))
        return price
        
    def _get_location(self, soup):
        loc = soup.find("h2",class_="gBaD1fLdPaNTbHErZvX7y")
        return self._scrub_html_field(loc)
        
    # date cleaner that removes all non-date text and recognises common words
    # for "available immediately"
    def _clean_date(self, cdate):
        cdate = self._scrub_html_field(cdate)
        cdate = re.sub("Added on ",'',cdate)
        cdate = re.sub("Reduced on ",'',cdate)
        cdate = re.sub("Added ",'',cdate)
        if cdate in ["Now","today"]: 
            return date.today().strftime("%d/%m/%Y")
        if(re.match(".*/.*/.*", cdate)):
            return cdate
        else:
            return "NaN"
        
    def _scrape_url(self, url):
        """_scrape_url(url) merges all extractor functions into one"""
        
        soup = self._make_soup(url)
        
        cdate = self._get_date_let(soup)
        price = self._get_price(soup)
        location = self._get_location(soup)
        date_added = self._get_date_added(soup)
        let_term = self._get_term(soup)
        furnished = self._get_furnished(soup)
        property_type = self._get_type(soup)
        bedrooms = self._get_bedrooms(soup)
        agency = self._get_agency(soup)
        
        return (price, cdate, property_type, bedrooms, location, furnished, 
                let_term, date_added, agency)
    
    def _sort_times(self, column):
        self.data.sort_values(by=[column],ascending=False,inplace=True)
    
    # convert date to proper format to allow ordering
    def _format_times(self, column, sort_by = True):
        self.data[column] = pd.to_datetime(self.data[column],
                                                     format="%d/%m/%Y")
        if sort_by is True:
            self._sort_times(column)
            
        self.data[column] = self.data[column].dt.strftime("%d/%m/%Y")

    def __init__(self, urls, verbose=True):
        for i in urls:
            if verbose is True: print(i)
            self.results[i] = self._scrape_url(i)
        self.data = pd.DataFrame.from_dict(self.results,orient="index")
        self.data.reset_index(level=0, inplace=True)
        self.data.columns = ["URL","Price", "Available from", "Property type",
                             "Bedrooms", "Location", "Furnished", "Let term", 
                             "Date added online", "Agency"]
        
        self.data["Date added to spreadsheet"] = date.today().strftime("%d/%m/%Y")
        
        self._format_times("Available from")
        self._format_times("Date added online", sort_by = False)
        self._format_times("Date added to spreadsheet", sort_by = False)
        
    def get_df(self):
        return self.data
        
class CombinedResults:
    """CombinedResults automatically detects all offers from a URL and 
    scrapes and saves the results to a tsv file. If the output file already
    exists, it will be read in first. Then, expired offers and removed and 
    new offers appended appended.
    It can also take a list of URLs, for example for different cities, and 
    process them all into one, keeping only unique offers.
    
    Usage:
        overview_url = "https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=REGION%5E93598"
        output_file = "test.tsv"
        CombinedResults(overview_url, output_file, overwrite=False)
    """
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
            self.res = res.get_df()
        else:
            ex = pd.read_csv(path_to_existing, sep="\t")
            
            # remove offers no longer present on the site
            ex = ex.query("URL in @links")
            
            links = [i for i in links if i not in ex.iloc[:,0].values]
            if len(links) > 0:
                res = ResultsScraper(links)
                
            else:
                print("No new offers detected. Will quit without update.")
                exit(0)
            
            out = ex.append(res.data, ignore_index = True)
            self.res = out
        
        self._format_times("Available from")
        self._format_times("Date added online", sort_by = False)
        self._format_times("Date added to spreadsheet", sort_by = False)
        
    def write_out(self, out_path, overwrite=True):
        if os.path.exists(out_path) and overwrite is not True:
            raise FileExistsError(f"{out_path} exists and overwrite=False")
        else:
            self.res.to_csv(out_path, sep="\t",index=False)
          
@Gooey(advanced=False,
       auto_start=False,
       program_name="Rightmove Scraper",
       default_size=(1300,700), 
       required_cols = 1,
       menu = [{
                "type": "AboutDialog",
                "menuTitle": "About",
                "name": "Rightmove Scraper",
                "description": "Save time and extract rental offers from rightmove into a nice table!",
                "version": "0.2",
                "copyright": "2021",
                "website": "https://github.com/jeskowagner/rightmove_scraper_gui",
                "developer": "http:/github.com/jeskowagner"
            }])

# for interactive use, implements a GUI that automates almost all of the process.
def main():
    parser = GooeyParser()
    parser.add_argument("url",  widget = "TextField", help = "Your search URL. See the manual for details.")
    parser.add_argument("outfile", widget = "FileSaver", help="File to store the results in.")
    args = parser.parse_args()
    links = [args.url]
    out = args.outfile
    cr = CombinedResults(links, out)
    cr.write_out(out, overwrite=True)
    
# catch either way to call main
if __name__ == "__main__":
    main()
    
# base = "https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=REGION%5E{CODE}&minBedrooms=2&maxPrice=1200&minPrice=500&propertyTypes=&maxDaysSinceAdded=14&includeLetAgreed=false&mustHave=&dontShow=retirement%2ChouseShare&furnishTypes=&letType=longTerm&keywords="
# https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=REGION%5E93598&minBedrooms=2&maxPrice=1200&minPrice=500&propertyTypes=&maxDaysSinceAdded=14&includeLetAgreed=false&mustHave=&dontShow=retirement%2ChouseShare&furnishTypes=&letType=longTerm&keywords=
# regions = [93598,66970,66978]
# links = [base.format(CODE=i) for i in regions]

# out = "/home/jesko/projects/rightmove_scaper/scrape_results.tsv"

# cr = CombinedResults(links,path_to_existing=out)
# cr.write_out(out, overwrite=True)
