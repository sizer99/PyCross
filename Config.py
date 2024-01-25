# ----------------------------------------------------------------------------
# Reading the config file and return a Config class
# ----------------------------------------------------------------------------

import argparse, sys
from enum import Enum


class Config:
    """Config parsed from the infile"""
    
    def __init__( self, rown: int, coln: int ) -> None:
        self.rown           :int        = rown
        self.coln           :int        = coln
        self.args                       = None          # argparse - will be set by read_config_file
        self.outfile                    = None          # output file, if asked for
        self.rows  :list[ list[int] ]   = [ [] for i in range(rown) ] # Empty for now
        self.cols  :list[ list[int] ]   = [ [] for i in range(coln) ] #    These are [ [1, 3, 2], [], [10], etc ] one per row/col
        self.row_hdrs       :list[str]  = [ ]           # will generate after reading config file
        self.col_hdrs       :list[str]  = [ ]           #    Both are just the text to add, can be generated up front 
        self.row_hdr_width  :int        = 1             # till we read otherwise from config file
        self.col_hdr_height :int        = 1
        

class ParseState( Enum ):
    SIZE        = 1
    ROWHEADER   = 2
    ROWS        = 3
    COLHEADER   = 4
    COLS        = 5
    DONE        = 6
    
def read_config_file( args: argparse.Namespace ):
    
    # open the file
    try: 
        with open( args.infile ) as f:
            lines = [ l.strip() for l in f.readlines() ]
    except Exception as ex:
        print( f"*** Couldn't open {args.infile}:", file = sys.stderr )
        print( f"{ex}", file = sys.stderr )
        sys.exit( 1 )
    
    state :ParseState = ParseState.SIZE
    line_no = 0
    for line in lines:
        line_no += 1
        # print( state, line )        

        # skip comments
        if line.startswith( "#" ) or line.startswith( ";" ) or line.startswith( "//" ):
            continue
        
        match state:
            # expect [rows] x [cols] 
            case ParseState.SIZE:
                if line == "":
                    continue
                rc = line.split( 'x' )
                try:
                    rown, coln = int( rc[0] ), int( rc[1] )
                except Exception as ex:    # probably ValueError
                    print( f"Line {line_no}: '{line}':  expected '[rows]x[cols]' like '10x10'", file = sys.stderr )
                    sys.exit( 2 )
                if rown < 1 or coln < 1:
                    print( f"Line {line_no}: '{line}':  [rows]x[cols] must be positive non-zero!", file = sys.stderr )
                    sys.exit( 2 )
                # print( f"{coln} x {rown}")
                config          = Config( rown, coln )
                config.args     = args
                state           = ParseState.ROWHEADER
             
            case ParseState.ROWHEADER:
                if line == "":
                    continue
                uline = line.upper()
                if uline != "ROWS:":
                    print( f"Line {line_no}: '{line}':  expected 'Rows:' header", file = sys.stderr )
                    sys.exit( 2 )
                state       = ParseState.ROWS
                idx :int    = 0
            
            case ParseState.ROWS:
                r : list[int] = config.rows[ idx ]
                width :int = 1
                if line != "0":     # allow just '0' as blank line
                    try:
                        split = line.replace( ',', ' ' ).split( ' ' )   # split on , or space
                        for s in split:
                            n = int( s )
                            if n < 1:
                                print( f"Line {line_no}: '{line}': each Rows entry must be positive non-zero integer!", file = sys.stderr )
                                sys.exit( 2 )
                            r.append( n )
                            width += 2   # the number and a space
                            if n > 9:
                                width += 1
                    except Exception as ex:
                        print( f"Line {line_no}: '{line}': each Rows entry must be positive non-zero integer!", file = sys.stderr )
                        sys.exit( 2 )
                if width > config.row_hdr_width:
                    config.row_hdr_width = width
                idx += 1
                if idx >= config.rown:
                    state = ParseState.COLHEADER
            
            case ParseState.COLHEADER:
                if line == "":
                    continue
                uline = line.upper()
                if uline != "COLS:" and uline != "COLUMNS:":
                    print( f"Line {line_no}: '{line}':  expected 'Cols:' or 'Columns:' header", file = sys.stderr )
                    sys.exit( 2 )
                state = ParseState.COLS
                idx   = 0
            
            case ParseState.COLS:
                c = config.cols[ idx ]
                height  = 0
                if line != "0":     # allow just '0' as blank line
                    try:
                        split = line.replace( ',', ' ' ).split( ' ' )   # split on , or space
                        for s in split:
                            n = int( s )
                            if n < 1:
                                print( f"Line {line_no}: '{line}': each Cols entry must be positive non-zero intenger!", file = sys.stderr )
                                sys.exit( 2 )
                            c.append( n )
                            height += 2         # number, then maybe space
                            if n > 9:
                                height += 1     # need second digit
                    except Exception as ex:
                        print( f"Line {line_no}: '{line}': each Cols entry must be positive non-zero intenger!", file = sys.stderr )
                        sys.exit( 2 )
                height -= 1   # one of them doesn't need a space
                if height > config.col_hdr_height:
                    config.col_hdr_height = height
                idx += 1
                if idx >= config.coln:
                    state = ParseState.DONE

            case ParseState.DONE:
                if line == "":
                    continue
                uline = line.upper()
                if uline != "DONE":
                    print( f"Line {line_no}: '{line}': expected 'DONE'", file = sys.stderr )
                    sys.exit( 2 )
        # end of match state

        if args.outfile:
            try: 
                config.outfile = open( args.outfile, 'w' )
            except Exception as ex:
                print( f"*** Couldn't open output file '{args.outfile}':", file = sys.stderr )
                print( f"{ex}", file = sys.stderr )
                sys.exit( 3 )
                

    # We've parsed everything, now generate the row and column headers

    # rows are easy, just add them as we generate them
    for y in range( config.rown ):
        hdr = ""
        for n in config.rows[y]:
            hdr = hdr + str(n) + " "
        hdr = hdr.rjust( config.row_hdr_width )
        config.row_hdrs.append( hdr + "|" )
    
    # cols are harder - they need to be basically rotated 90
    # [ 1, 2, 3, 2 ]  "1| | "   
    # [ 4,  4 ]   ->  " | | "
    # [ 10, 2 ]       "2| | " 
    #                 " | |1"
    #                 "3|4|0"              
    #                 " | | "
    #                 "2|4|2"
    #                 "--------"
    hdrs = [ [ ' ' for x in range(config.coln) ] for y in range(config.col_hdr_height) ]  # [ [line 1 entries ], [ line 2 entries ], ... ]
    for x in range(config.coln):               # for each col header
        y = config.col_hdr_height - ( len(config.cols[x]) * 2 - 1 )  # leave room for spaces
        for n in config.cols[x]:    # leave space for 2 digit numbers
            if n >= 10:
                y -= 1
        for n in config.cols[x]:
            if n >= 10:
                hdrs[y][x] = str( int( n/10 ) )
                n = n % 10
                y += 1
            hdrs[y][x] = f"{n}"
            y += 2
    # now just join then with |
    left = " " * len( config.row_hdrs[0] )
    for y in range( config.col_hdr_height ):
        # enough on the left for row headers
        config.col_hdrs.append( left + "|".join( hdrs[y]) )
    # and add a "--------------" at the bottom
    config.col_hdrs.append( left.ljust( len( config.col_hdrs[0] ), '-' ) )

    return config

