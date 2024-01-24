
#!python
# ----------------------------------------------------------------------------
# Simple Picross Solver
#
# Text output only!
#
# Package dependencies:  colorama, numpy
#
# Copyright 2024 Ron Dippold
# ----------------------------------------------------------------------------

VERSION = 0.01

# import standard libs
import argparse
from enum import Enum
import sys

# import installed packages
from colorama import Fore, Back, Style
import numpy

# import my packages
from Config import Config, read_config_file

global config
config = None    # class Config

# ----------------------------------------------------------------------------
# Our Solve Exceptions
# ----------------------------------------------------------------------------
class SolveError( Exception ):
    def __init__( self, message ):
        super().__init__(message)

# ----------------------------------------------------------------------------
# A board state
# ----------------------------------------------------------------------------

class Board:
    """Board state for one move"""
    
    # Cell states
    UNKNOWN = 0
    FILLED  = 1
    BLANK   = 2
    
    def __init__( self ):
        self.grid           :numpy.array    = None      # the board state
        self.step           : int           = 1         # what solving step
        self.row_solved     :numpy.array    = None      # whether each row is solved and can be ignored    
        self.col_solved     :numpy.array    = None      # whether each col is solved and can be ignored
    
    # make a new blank board
    def blank() -> 'Board':
        "Return new blank Board"
        board               = Board()
        board.step          = 1
        board.grid          = numpy.zeros( ( config.rown, config.coln ), numpy.uint8 )   # 0 is UNKNOWN
        board.row_solved    = numpy.zeros( config.rown, numpy.uint8 )
        board.col_solved    = numpy.zeros( config.coln, numpy.uint8 )
        #board.row_solved    = [ False ] * config.rown
        #board.col_solved    = [ False ] * config.coln
        return board
       
    def copy( self ) -> 'Board':
        "Return deep copy Board from passed Board"
        board = Board()
        board.grid          = numpy.copy( self.grid )
        board.row_solved    = numpy.copy( self.row_solved )
        board.col_solved    = numpy.copy( self.col_solved )
        board.step          = self.step + 1
        #board.row_solved    = [ b for b in self.row_solved ]
        #board.col_solved    = [ b for b in self.col_solved ]
        return board

    #
    # return printable copy
    #
    UNKNOWN_STR         = ". "
    UNKNOWN_STR_ANSI    = Style.DIM + UNKNOWN_STR + Style.RESET_ALL
    FILLED_STR          = "* "
    FILLED_STR_ANSI     = Style.BRIGHT + Back.WHITE + "  " + Style.RESET_ALL
    BLANK_STR           = "  "
    BLANK_STR_ANSI      = BLANK_STR
    cell_strs           = [ UNKNOWN_STR, FILLED_STR, BLANK_STR ]
    cell_strs_ansi      = [ UNKNOWN_STR_ANSI, FILLED_STR_ANSI, BLANK_STR_ANSI ]

    def printable( self, console:bool ) -> list[str]:
        lines = []
        # just add the column headers - easy
        lines += config.col_hdrs

        # add the step # in the upper left
        step_str = f"{self.step:>4}"
        step_len = len( step_str )  # before we add ANSI
        if console:
            step_str = Fore.CYAN + step_str + Style.RESET_ALL
        lines[0] = step_str + lines[0][step_len:]

        # decide to use ANSI strings (for console) or non-ANSI (for file)
        strs = self.cell_strs_ansi if console else self.cell_strs
        # for each row
        for y in range( config.rown ):
            # start a new line with the row header
            line = [ config.row_hdrs[y] ]
            # for each col
            for x in range( config.coln ):
                # add the cell state
                line.append( strs[ self.grid[y,x] ])
            # then join all the cells for the final line
            lines.append(  "".join( line ) )
        lines.append( "" )    # and a blank
        return lines
    

    def solve_slice( self, slice :numpy.array, hints :list[int] ) -> ( bool, bool ):
        """
        Try to knock out items in a row or column, we don't care which one.  
        May modify slice directly. Returns ( changed?, done? )
        """
        
        count = len(slice)

        #
        # rule 'zero' - 0 length means we're done
        #
        if not hints:
            slice.fill( self.BLANK )
            return ( True, True )
        
        #
        # rule full - hints just fit
        #
        left = 0
        while( slice[left] == self.BLANK ):
            left += 1
        right = count - 1
        while( slice[right] == self.BLANK ):
            right -= 1
        available = right - left + 1
        if available == 0:  # should not get here, but handle it as a done row
            return( True, True )
        hints_len = sum( hints ) + len( hints ) - 1
        if hints_len > available:
            print( f"Hints ({hints_len}) are larger than available space ({available})" )
            raise SolveError( f"Hints ({hints_len}) are larger than available space ({available})" )
        if hints_len == available:  # the whole line is filled, hooray!
            for hint in hints:
                for x in range(hint):
                    slice[left] = self.FILLED
                    left += 1
                if left < count:    # last one may be at end
                    slice[left] = self.BLANK
                    left += 1
            return( True, True )
        
        return ( False, False )


    def solve_next( self ) -> ( 'Board', bool, bool, bool ):
        """
        Try to find the next changes in the board, returns ( new board, changed?, done?, dead? )
           new_board may be the same as the old board. It is for now!
        """
        
        changes   :bool = False
        rows_done :int  = 0
        cols_done :int  = 0
        
        board.step += 1

        # do rows
        for y in range( config.rown ):
            if self.row_solved[y]:
                rows_done += 1
                continue
            row = self.grid[y]    # get row y
            try:
                ( changed, done ) = self.solve_slice( row, config.rows[ y ] )
            except SolveError as ex:
                print( f"{Style.BRIGHT}{Fore.RED}* {Style.RESET_ALL} Row {y+1} ( {config.rows[y]} ):" )
                print( ex )
                return( board, False, False, True )
                
            if changed:
                changes = True
                self.grid[y] = row
            if done:
                self.row_solved[y] = True
                rows_done += 1
            
        # do cols            
        for x in range( config.coln ):
            if self.col_solved[x]:
                cols_done += 1
                continue
            col = self.grid[:,x]    # get col x
            try:
                ( changed, done ) = self.solve_slice( col, config.cols[ x ] )
            except SolveError as ex:
                print( f"{Style.BRIGHT}{Fore.RED}* {Style.RESET_ALL} config {y+1} ( {config.cols[y]} ):" )
                print( ex )
                return( board, False, False, True )
            if changed:
                changes = True
                self.grid[:,x] = col
            if done:
                self.col_solved[x] = True
                cols_done += 1
        
        done = ( rows_done == config.rown ) and ( cols_done == config.coln )
        return ( board, changes, done, False )
            


# ----------------------------------------------------------------------------
# Output to console and/or file
# ----------------------------------------------------------------------------
    
def output( str ):
    if not config.args.quiet:
        print( str )
    if config.outfile:
        print( str, file = config.outfile )
    


# ----------------------------------------------------------------------------
# Main function, argument handling
# ----------------------------------------------------------------------------


if __name__ == "__main__":
    
    print( f"{Fore.GREEN}{Style.BRIGHT}PyCross {VERSION:.2f}{Fore.WHITE}")
    
    # parse the user args
    parser = argparse.ArgumentParser()
    parser.add_argument( "infile",              help = "file that describes the nonogram" )
    parser.add_argument( "-H", "--filehelp",    help = "show expected infile format", dest="filehelp", action = "store_true" )
    parser.add_argument( "-v", "--verbose",     help = "be more verbose", dest="verbose", action = "store_true" )
    #parser.add_argument( "-l", "--lines",       help = "print lines between rows and columns", dest="lines", action = "store_true" )
    parser.add_argument( "-p", "--per-line",    help = "how many solve steps to show per line", dest="perline", type = int, default = 1 )
    parser.add_argument( "-o", "--out-file",    help = "also write output to specified file", dest="outfile", default = "" )
    parser.add_argument( "-q", "--quiet",       help = "don't even write output to console", dest="quiet", action = "store_true" )
    
    args = parser.parse_args()
    
    if args.filehelp:
        print( "Comment lines starting with # or // will be ignored:" )
        print( "    // A lovely swan" )
        print( "Blank lines are ignored EXCEPT in Rows: and Cols: sections, where they are valid entries." )
        print( "The first non-comment line of the file should be [rows]x[columns]:" )
        print( "    10x10" )
        print( "The next line must be 'rows:' (case insensitive):" )
        print( "    Rows:" )
        print( "Then each line should have the space separated numbers for the next row:" )
        print( "    1 3 2" )
        print( "    2 2     [etc]" )
        print( "After one line for each row, the next line must be 'cols:' or 'columns:' (space insensitive):" )
        print( "    Cols:" )
        print( "Then each line should have the space separated numbers for the next col:" )
        print( "    0" )
        print( "    4 3 1   [etc]" )
        print( "Note you can use just '0' or a blank line for '0 filled', but you can't use '3 0 2'" )
        print( "Finally, 'Done' (case insensitive):" )
        print("     Done" )
        print( "And that's it!")
        sys.exit( 1 )
    
    config = read_config_file( args )
    
    output( f"\n* {Fore.CYAN}{args.infile}{Style.RESET_ALL} - {Fore.BLUE}{Style.BRIGHT}{config.rown} rows x {config.coln} cols{Style.RESET_ALL}\n")
    
    board = Board.blank()
    
    while True:
        # TODO: Combine lines for --per-line
        if not args.quiet:
            lines = board.printable( console=True )
            print( "\n".join( lines ) )
        if config.outfile:
            lines = board.printable( console=False )
            config.outfile.writelines( lines )
        ( new_board, changed, done, dead ) = board.solve_next()
        # print( changed, done, dead )
        if dead: 
            break
        if done:
            print( f"{Fore.GREEN}{Style.BRIGHT}SOLVED!{Style.RESET_ALL}" )
            break
        if not changed:
            print( f"{Fore.RED}{Style.BRIGHT}Unsolved, but couldn't find anything else to do.{Style.RESET_ALL}" )
            break
        board = new_board      # might be the same anyhow
        
        
    
    
    

    
    
        
    
    
    
    
    

