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

VERSION = 1.02

# import standard libs
import argparse
from   enum import Enum
import random
import sys
import time
import traceback

# import installed packages
try:
    from   colorama import Fore, Back, Style
    import numpy
except Exception as ex:
    print( "*** You need colorama and numpy installed for this." )
    print( "   pip install colorama numpy" )
    sys.exit(10)

# import my packages
from   Config import Config, read_config_file

global config
config :'Config' = None


# verbose levels
VERBOSE_NONE = 0
VERBOSE_SOME = 1
VERBOSE_MORE = 2
VERBOSE_ALL  = 5        # leave room

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
        self.row_changed    :numpy.array    = None      # whether each row has had changes
        self.col_changed    :numpy.array    = None      # whether each col has had changes
        self.row_moves      :numpy.array    = None      # how many possible moves in this row if not done
        self.col_moves      :numpy.array    = None      # how many possible moves in this col if not done
        self.forced         :list           = []        # forced moves we've tried
    
    # make a new blank board
    def blank() -> 'Board':
        "Return new blank Board"
        board               = Board()
        board.step          = 1
        board.grid          = numpy.zeros( ( config.rown, config.coln ), numpy.uint8 )   # 0 is UNKNOWN
        board.row_solved    = numpy.zeros( config.rown, numpy.uint8 )       # nothing has been solved
        board.col_solved    = numpy.zeros( config.coln, numpy.uint8 )
        board.row_changed   = numpy.ones(  config.rown, numpy.uint8 )       # everything has changed!
        board.col_changed   = numpy.ones(  config.rown, numpy.uint8 )
        board.row_moves     = numpy.zeros( config.rown, numpy.uint32 )
        board.col_moves     = numpy.zeros( config.rown, numpy.uint32 )
        return board
       
    def copy( self ) -> 'Board':
        "Return deep copy Board from passed Board"
        board = Board()
        board.grid          = numpy.copy( self.grid )
        board.row_solved    = numpy.copy( self.row_solved )
        board.col_solved    = numpy.copy( self.col_solved )
        board.row_changed   = numpy.copy( self.row_changed )
        board.col_changed   = numpy.copy( self.col_changed )
        board.row_moves     = numpy.copy( self.row_moves )
        board.col_moves     = numpy.copy( self.col_moves )
        board.step          = self.step + 1
        board.forced        = self.forced
        return board

    #
    # Class methods
    # 
    def get_all_positions( left :int, right :int, hints :list[int] ) ->  list[int]:
        """
        Given a starting max left, a starting max right, and the hints, generate all possible
            fill positions.
        """
        # Figure out the (inclusive) left possible pos for each hint
        left2 = left                        # if left is 0 and hints is [ 1, 2, 3],
        hints_pos = [ ]                     #   hints_pos is [ 0, 2, 5 ]
        for h in hints:                     #  * _ * * _ * * * _ .
            hints_pos.append( left2 )
            left2 += h + 1  # for the BLANK
            
        # figure out the (inclusive) right possible pos for each hint
        right2 = right + 1                  # If right is 10 and hints is [ 1, 2, 3 ]
        hints_right_pos = []                #    hints_right_pos is [ 2, 4, 7 ]
        for h in reversed( hints ):         # . _ * _ * * _ * * *
            right2 -= h
            hints_right_pos.append( right2 )
            right2 -= 1  # for the BLANK
        hints_right_pos.reverse()
        
        # Start out in the left pos
        ridx            = len( hints ) - 1  # index of last hint
        idx             = ridx
        hints_pos[-1]  -= 1                 # move the last one left one so we can increment it at the start
        
        # print( f"Left: {left} Right: {right} Hints: {hints} Max: {hints_right_pos}")
        
        while True:
            hints_pos[idx] += 1             # move current index right
            if hints_pos[idx] > hints_right_pos[idx]:
                if idx == 0:                # We can't move the left hint any further right, stop
                    return
                idx -= 1
                continue
            if idx < ridx:                  # not on last hint?
                while idx < ridx:           # move the next indexes to their next possible positions
                    hints_pos[idx+1] = hints_pos[idx] + hints[idx] + 1  # next possible starting position
                    idx += 1
            yield hints_pos
            
    def get_slice_left_right_available( slice: numpy.array ) -> ( int, int, int ):
        """
        Count from the edges till we find a non-forced blank cell.
        Blank cells at the edge are basically forbidden territory, we can 'ignore' them.
        Returns (left, right, available)
        """
        full_width = len(slice)        

        left, right  = 0, full_width - 1
        while( left < full_width and slice[left] == Board.BLANK ):
            left += 1
        while( right > left and slice[right] == Board.BLANK ):
            right -= 1
        available = right - left + 1
        return( left, right, available )

    #
    # return/output printable copy
    #

    # all these are set by set_output_chars()
    UNKNOWN_STR, UNKNOWN_STR_ANSI, FILLED_STR, FILLED_STR_ANSI, BLANK_STR, BLANK_STR_ANSI = "","","","","",""
    cell_strs       = []
    cell_strs_ansi  = []
    
    def set_output_chars( args: argparse.Namespace ):
        Board.UNKNOWN_STR         = args.unknown_char[0] + " "
        Board.UNKNOWN_STR_ANSI    = Style.DIM + Board.UNKNOWN_STR + Style.RESET_ALL
        Board.FILLED_STR          = args.fill_char[0] + " "
        Board.FILLED_STR_ANSI     = Style.BRIGHT + Back.WHITE + " " + Style.RESET_ALL + " "
        Board.BLANK_STR           = args.blank_char[0] + " "
        Board.BLANK_STR_ANSI      = Board.BLANK_STR
        Board.cell_strs           = [ Board.UNKNOWN_STR, Board.FILLED_STR, Board.BLANK_STR ]
        Board.cell_strs_ansi      = [ Board.UNKNOWN_STR_ANSI, Board.FILLED_STR_ANSI, Board.BLANK_STR_ANSI ]

    def printable( self, console:bool ) -> list[str]:
        """ 
        Return printable copy of the board.
        Normally just use self.output_grid() instead - it prints to console and file as needed.
        """
        

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
        strs = Board.cell_strs_ansi if console else Board.cell_strs
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

    def output_grid( self ) -> None:
        if not config.args.quiet:
            lines = board.printable( console=True )
            print( "\n".join( lines ) )
        if config.outfile:
            lines = board.printable( console=False )
            config.outfile.write( "\n".join( lines ) )
            

    #
    # Board solving
    #
    
    def recursive_solve( self, slice :numpy.array, hints :list[int], rowcol :str, available :int, left: int, right: int, force :int ) -> ( list[int], int ):
        """
        This runs through all given options for a slice, then looks at
             where things overlapped. May modify slice directly.
        Not technically recursive since get_all_positions is a generator,
            just looks at every possible position.
        
        Don't call this directly in most cases, called by solve_slice() with same parms.
          left, right:  outermost non-BLANK position (where we have to start worrying)
          available = right - left : available width, ignoring BLANKs on edges
          force: If >= 0 force that possible move in --foprce mode
          
        Returns ( changed_cell_indexes[], possible_moves )
           possible_moves is invalid if force was >= 0 because we stopped at that combination
        """
        
        #
        #  Say we have the following line:
        #    2 1 | . . . . .
        #  The recursive options are:
        #          * * _ * _    and
        #          * * _ _ *    and
        #          _ * * _ *
        #            ^          this is the same in all, must be FILLED
        #  Or if we have the following:
        #      1 | . . . * .   (one already filled)
        #  the only possibility is:
        #          _ _ _ * _    so the rest must be BLANK and the row is done

        # if slice is all unknowns (0) and the hints are too short don't even bother trying.
        # Say the slice is 10 long and the hints are '1 2' then hints_width is 4,
        #    and 10 - 4 = 6 which is way longer than 1 or 2, so not worth it.
        # If the slice is 10 long and the hints are '1 2 3' then hints_width is 8,
        #    10 - 8 = 2, so it's worth it because we'll get overlap on the 3.
        if not slice.any():  # all UNKNOWN
            hints_width = sum( hints ) + len( hints ) - 1  # sum(n) + (n-1) spaces
            hints_max = max( hints )
            if ( available - hints_width ) >= hints_max:
                return ( [], 99 )  # 99 = lots of possible moves
            

        # count how many FILLED we have at each cell for every combination
        fill_count  = numpy.zeros( len(slice), dtype=numpy.uint32 )

        # Iterate over the possible positions
        pos_count = 0
        for fill_pos in Board.get_all_positions( left, right, hints ):

            if config.args.verbose >= VERBOSE_MORE:
                output(  f"  Step {self.step:>4} - {rowcol} - {left} {right} {hints} -  {pos_count} {fill_pos}")
           
            # Check if this position is possible
            #    iterate through each block and see if it's not illegal
            okay = True
            end  = 0
            for x in range( len(hints) ):
                pos, size = fill_pos[x], hints[x]
                if pos > end and numpy.any( slice[end:pos] == Board.FILLED ): # can't have any FILLED in before this
                    okay = False
                    break
                end  = pos + size  # one PAST the end
                if numpy.any( slice[pos:end] == Board.BLANK ):   # can't be on top of any be blank areas
                    okay = False
                    break
            if not okay:
                continue
            if end <= right and numpy.any( slice[end:] == Board.FILLED ):     # can't have any filled ones after we put all ours down
                continue

            #
            # force this position if requested
            #
            if pos_count == force:
                if config.args.verbose >= VERBOSE_SOME:
                    output( f"FORCING! {hints} {fill_pos} {slice[0:fill_pos[0]]}" )
                changed = []
                for x in range( len( hints ) ):
                    pos, size = fill_pos[x], hints[x]
                    end  = pos + size                   # one PAST the end
                    for x in range( pos, end ):
                        if slice[x] == Board.UNKNOWN:
                            slice[x] = Board.FILLED
                            changed.append(x)
                for x in range( left, right ):
                    if slice[x] == Board.UNKNOWN:
                        slice[x] = Board.BLANK
                        changed.append(x)
                return ( changed, pos_count )           # pos_count is invalid
                

            # count the number of legal positions
            pos_count += 1

            # mark the filled cells in fill_count
            for x in range( len(hints ) ):
                pos, size = fill_pos[x], hints[x]
                end  = pos + size                   # one PAST the end
                for x in range( pos, end ):
                    fill_count[x] += 1              # each filled in square
                    
            if config.args.verbose >= VERBOSE_ALL:
                output( f"       {pos_count}  fill: {fill_count}")

        if pos_count == 0:
            raise SolveError( f"* Step {self.step:>4} {rowcol} - hints ({hints}) - no possible solutions!" )

        # Now look for any previously UNKNOWN cells and see if they were always 
        #     BLANK or FILLED in our simulation
        changed = []
        for x in range( len( slice ) ):
            if slice[x] == Board.UNKNOWN:
                if fill_count[x] == pos_count:
                    slice[x] = Board.FILLED
                    changed.append(x)
                elif fill_count[x] == 0:
                    slice[x] = Board.BLANK
                    changed.append(x)
            
        return ( changed, pos_count )


    def solve_slice( self, slice :numpy.array, hints :list[int], rowcol :str, force :int ) -> ( list[int], int, bool ):
        """
        Try to knock out items in a row or column, we don't care which one. 
        
        Caller has already checked if row_done or col_done to see if we don't need to check this.
        
        If force >= 0 brute force that solution
        
        Returns ( changed_indexes[], valid_moves, done )
        """
        
        full_width = len(slice)

        #
        # rule 'zero' - 0 length means we're done
        #
        if not hints:
            slice.fill( Board.BLANK )
            if config.args.verbose >= VERBOSE_SOME:
                output(  f"- Step {self.step:>4} {rowcol} - 0 length fill BLANK" )
            # this only triggers on the first time, so just assume every cell changed
            return ( [ x for x in range(full_width) ], 0, True )
        # rule 'one' - 1 hint, full width - trivial
        #
        if len(hints) == 1 and hints[0] == full_width:
            slice.fill( Board.FILLED )
            if config.args.verbose >= VERBOSE_SOME:
                output(  f"- Step {self.step:>4} {rowcol} - {hints} FILLED" )
            # this only triggers on the first time, so just assume every cell changed
            return ( [ x for x in range(full_width) ], 0, True )
        
        left, right, available = Board.get_slice_left_right_available( slice )
        if available == 0:  # should not get here, but handle it as a done row
            return( [], 0, True )
        
        hints_total = sum( hints ) + len( hints ) - 1
        if hints_total > available:
            # print( f"Hints ({hints_len}) are larger than available space ({available})" )
            raise SolveError( f"* Step {self.step:>4} {rowcol} - hints ({hints}) are larger than available space ({available})" )
        if hints_total == available:  # the whole line is filled, hooray!
            changed = []            # this can kick in later as left and right move in, look for actual changes
            if config.args.verbose >= VERBOSE_SOME:
                output(  f"- Step {self.step:>4} {rowcol} - {hints} fills it perfectly" )
            for hint in hints:
                # set the FILLED section
                # slice[left:left+hint] = Board.FILLED    # can't get changes this way
                for x in range( left, left+hint ):
                    if slice[x] != Board.FILLED:
                        slice[x] = Board.FILLED
                        changed.append( x )
                left += hint
                if left < full_width:    # Add a blank if we're not at end
                    if slice[left] != Board.BLANK:
                        slice[left] = Board.BLANK
                        changed.append( left )
                    left += 1
            return ( changed, 0, True )

        # The big hammer
        ( changed_idxs, valid_moves ) = self.recursive_solve( slice, hints, rowcol, available, left, right, force )
        if not changed_idxs:
            return ( changed_idxs, valid_moves, False )
        
        # check if line is done from the big hammer
        idx = -1                        # haven't found one yet
        fills = False
        found = []
        for x in range( full_width ):
            if not fills:               # we were not in filled area, look for one
                if slice[x] == Board.FILLED:
                    fills = True
                    found.append(1)     # 1 block fill so far
                    idx += 1
                    if idx >= len( hints ):
                        raise SolveError( f"* Step {self.step:>4} {rowcol} - {slice} exceeds {hints}" )
                    continue
            else:                       # we were in a filled area, look for non-filled
                if slice[x] == Board.FILLED: # continuing filled
                    found[idx] += 1
                else:
                    fills = False
                    if found[idx] != hints[idx]:
                        break
        
        # We're done!
        if found == hints:
            if config.args.verbose >= VERBOSE_SOME:
                output(  f"- Step {self.step:>4} - {rowcol} - done" )
            for x in range( full_width ):
                if slice[x] == Board.UNKNOWN:
                    slice[x] = Board.BLANK
                    changed_idxs.append( x )
            return ( changed_idxs, valid_moves, True )
        
        return( changed_idxs, valid_moves, False )
           

    def solve_next( self ) -> ( bool, bool, bool ):
        """
        Try to find the next changes in the board, returns ( changed?, done?, dead? )
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
            if not self.row_changed[y]: # not done but don't bother
                continue
            rowstr = f"Row {y+1:>2}"
            row = self.grid[y]    # get row y
            ( changed, valid_moves, done ) = self.solve_slice( row, config.rows[ y ], rowstr, -1 )
            self.row_moves[y]               = valid_moves
            if changed:
                if config.args.verbose >= VERBOSE_MORE:
                    self.output_grid()
                    
                changes                     = True
                self.grid[y]                = row
                self.row_changed[y]         = True
                for idx in changed:                 # changes in a row change columns!
                    self.col_changed[idx]   = True
            if done:
                self.row_solved[y]          = True
                rows_done += 1
            else:
                if not numpy.any( row == Board.UNKNOWN ):
                    if config.args.verbose >= VERBOSE_SOME:
                        output( f"- Step {self.step:>4} - {rowstr} - no unknowns, marking done" )
                    self.row_solved[y]      = True
                    rows_done += 1
            
        # do cols            
        for x in range( config.coln ):
            if self.col_solved[x]:
                cols_done += 1
                continue
            if not self.col_changed[x]:
                continue
            colstr = f"Col {x+1:>2}"
            col = self.grid[:,x]    # get col x
            ( changed, valid_moves, done ) = self.solve_slice( col, config.cols[ x ], colstr, -1 )
            self.col_moves[x] = valid_moves
            if changed:
                if config.args.verbose >= VERBOSE_MORE: 
                    self.output_grid()
                changes                     = True
                self.grid[:,x]              = col
                self.col_changed[x]         = True
                for idx in changed:
                    self.row_changed[idx]   = True
            if done:
                self.col_solved[x]          = True
                cols_done += 1
            else:
                if not numpy.any( col == Board.UNKNOWN ):
                    if config.args.verbose >= VERBOSE_SOME:
                        output( f"- Step {self.step:>4} - {colstr} - no unknowns, marking done" )
                    self.col_solved[x]      = True
                    cols_done += 1
        

        if config.args.verbose >= VERBOSE_ALL:
            output( f" rows_done {self.row_solved}   cols_done {self.col_solved}" )

        done = ( rows_done == config.rown ) and ( cols_done == config.coln )
        return ( changes, done, False )
    

    def force_random_move( self ):
        """
        Not strictly random - weighted for the rows/cols with the fewest moves available.
        Picks one with few moves and makes a random move.
        """

        # weight every row and column on the number of moves available (fewer is more weight)
        total = 0
        choices = []
        max_choices = max( self.row_moves + self.col_moves )
        for y in range(config.rown):
            if not self.row_solved[y]:
                weight = max_choices - self.row_moves[y]
                choices.append( [ weight, y ] )
                total += weight
        for x in range(config.coln):
            if not self.col_solved[x]:
                weight = max_choices - self.col_moves[x]
                choices.append( [ weight, x + 1000 ] )
                total += weight
        choices.sort( reverse=True )
        
        # might have to do this a couple times to get a legal one
        tried = set()
        while True:
        
            # generate a random number and see where that lands in all the choices
            r = random.randrange( 0, total )
            if r in tried:      # tried this before - TODO: check for too many repeats
                continue
            tried.add( r )
            
            if config.args.verbose >= VERBOSE_MORE:
                output( f" {r} of {total} in {choices}" )
            for ( weight, which ) in choices:
                if r > weight:
                    r -= weight
                    continue
                # found it!
                weight = max_choices - weight
                orig_grid = self.grid.copy()    # make a copy of the grid, because we might force something bad
                if which < 1000:  # a row
                    row = self.grid[which]
                    rowcol = f"Row {which:>2}"
                    # get the exact number of moves possible right now
                    ( changed_idx, moves, done ) = self.solve_slice( row, config.rows[which], rowcol, weight )
                    # and choose a random one
                    move = random.randrange( 0, moves )
                    if config.args.verbose >= VERBOSE_MORE:
                        output( f"-  Forcing Row {which:>2} move {move}" )
                    ( changed_idx, dummy, done ) = self.solve_slice( row, config.rows[which], rowcol, move )
                    self.grid[which] = row
                    # Check that we didn't do anything bad in the changed cols
                    okay = True
                    for idx in changed_idx:
                        if not Board.slice_is_legal( self.grid[:,idx], config.cols[idx] ):
                            if config.args.verbose >= VERBOSE_MORE:
                                output( f"    Causes Col {idx:>2} to be illegal, reverting" )
                            okay = False
                            break
                    if not okay:
                        self.grid = orig_grid   # put it back
                        continue
                            
                else: # a col
                    which -= 1000
                    col = self.grid[ :, which]
                    rowcol = f"Col {which:>2}"

                    # get the exact number of moves possible right now
                    ( changed_idx, moves, done ) = self.solve_slice( col, config.cols[which], rowcol, weight )
                    # and choose a random one
                    move = random.randrange( 0, moves )
                    output( f"-  Forcing Col {which:>2} move {move}" )
                    ( changed_idx, dummy, done ) = self.solve_slice( col, config.cols[which], rowcol, move )
                    self.grid[ :, which ] = col
                    # Check that we didn't do anything bad in the changed rows
                    okay = True
                    for idx in changed_idx:
                        if not Board.slice_is_legal( self.grid[idx], config.rows[idx] ):
                            if config.args.verbose >= VERBOSE_MORE:
                                output( f"    Causes Row {idx:>2} to be illegal, reverting" )
                            okay = False
                            break
                    if not okay:
                        self.grid = orig_grid   # put it back
                        continue

                if done:
                    self.row_solved[which] = True
                return
    
    def slice_is_legal( slice :numpy.array, hints :list[int] ) -> bool:
        """
        Looks at the hints to decide if what's in the slice is even legal.
        """

        # degenerate but fast case: no hints, nothing must be filled
        if not hints:
            ok = not numpy.any( slice == Board.FILLED )
            if not ok:
                print( f"{hints} {numpy.any( slice == board.FILLED) } {slice}")
                sys.exit(1)
            return ok

        left, right, available = Board.get_slice_left_right_available( slice )
        
        # Iterate over the possible positions
        # Iterate over the possible positions
        for fill_pos in Board.get_all_positions( left, right, hints ):
            okay = True
            end  = 0
            for x in range( len(hints) ):
                pos, size = fill_pos[x], hints[x]
                if pos > end and numpy.any( slice[end:pos] == Board.FILLED ): # can't have any FILLED in before this
                    okay = False
                    break
                end  = pos + size  # one PAST the end
                if numpy.any( slice[pos:end] == Board.BLANK ):   # can't be on top of any be blank areas
                    okay = False
                    break
            if not okay:
                continue
            if end < right and numpy.any( slice[end:] == Board.FILLED ):     # can't have any filled ones after we put all ours down
                continue
            
            # if we're here it's legal
            return True
        
        return False        # didn't find a single legal one
    

    def check_all_legal( self ) -> None:
        "Raises a SolveError if a Row or Col is illegal"
    
        for y in range(config.rown):
            if config.rows[y]:
                continue
            row = self.grid[y]
            if not Board.slice_is_legal( row, config.rows[y] ):
                raise SolveError( f"Row {y:>2} illegal" )
        
        for x in range(config.coln):
            if config.cols[x]:
                continue
            col = self.grid[:,x]
            if not Board.slice_is_legal( col, config.cols[x] ):
                raise SolveError( f"Col {x:>2} illegal" )
       
            


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
    parser.add_argument( "-v", "--verbose",     help = "be more verbose", dest="verbose", action="count", default=0 )
    #parser.add_argument( "-p", "--per-line",    help = "how many solve steps to show per line", dest="perline", type = int, default = 1 )
    parser.add_argument( "-o", "--out-file",    help = "also write output to specified file", dest="outfile", default = "" )
    parser.add_argument( "-q", "--quiet",       help = "don't even write output to console", dest="quiet", action = "store_true" )
    parser.add_argument( "-f", "--force",       help = "brute force solve if not enough info given", dest="force", action = "store_true" )
    parser.add_argument( "--seed",              help = 'set random seed for --force', dest='seed', type = int, default=42 )
    
    parser.add_argument( "--uc", "--unknown-char", help = 'a *single* character for unknown cells', dest='unknown_char', default='.' )
    parser.add_argument( "--fc", "--fill-char",    help = 'a *single* character for filled cells',  dest='fill_char', default='*' )
    parser.add_argument( "--bc", "--blank-char",   help = 'a *single* character for blank cells',   dest='blank_char', default='-' )
    
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

    # set seed if specified - otherwise whatever
    if args.seed:
        random.seed( args.seed )

    # Create the initial board and read the config file
    Board.set_output_chars( args )
    config = read_config_file( args )
    
    if not config.args.quiet:
        print( f"\n* {Fore.CYAN}{args.infile}{Style.RESET_ALL} - {Fore.BLUE}{Style.BRIGHT}{config.rown} rows x {config.coln} cols{Style.RESET_ALL}\n")
    if config.outfile:
        print( f"\n* {args.infile} - {config.rown} rows x {config.coln} cols\n", file=config.outfile )
    
    board      = Board.blank()
    start_time = time.time()
    board_prev = None

    try:
        done = False    
        while True:
            # TODO: Combine lines for --per-line

            board.output_grid()
            if done:
                break

            try:
                ( changed, done, dead ) = board.solve_next()
                board.check_all_legal()
            except SolveError as ex:
                print( f"* {Fore.RED}{ex}{Style.RESET_ALL}" )
                if config.outfile:
                    print( f"* {ex}", file=config.outfile )
                if args.force:
                    if board_prev:
                        # We used to keep a stack and pop back, but it's likely as anything that the
                        # first random forced move was wrong and we could spend immense amounts of time
                        # chasing down a board where the very first random move was totally wrong, so
                        # just go back to the first known good board.
                        output( f"    Reverting to previous board {board.step}" )
                        board = board_prev.copy()
                    else:
                        output( "* No previous board? Failing!")
                else: 
                    break
                
            # print( changed, done, dead )
            if dead: 
                break

            if done:
                end_time = time.time()
                solve_secs = end_time - start_time
                print( f"\n*** {Fore.GREEN}{Style.BRIGHT}SOLVED!{Style.RESET_ALL} - {solve_secs:0.2f}s" )
                if config.outfile:
                    print( f"\n--- SOLVED! - {solve_secs:.2f}s", file=config.outfile )
                if args.quiet:          # doesn't get printed otherwise
                    lines = board.printable( console=True )
                    print( "\n".join( lines ) )
                
            if not done and not changed:
                board.output_grid()
                print( f"{Fore.RED}{Style.BRIGHT}Unsolved, but couldn't find anything else to do.{Style.RESET_ALL}" )
                if config.outfile:
                    print( f"* Unsolved, but couldn't find anything else to do.", file=config.outfile )
                
                if args.force:
                    if not board_prev:  # only set the 'last known good board' if we haven't been forcing it
                        board_prev = board.copy()
                        output( "board_prev set!" )
                    output( f"- Switching to brute force" )
                    while True:
                        board = board.copy()
                        try:
                            board.force_random_move()
                            break
                        except SolveError as ex:
                            continue
                        except Exception as ex:
                            print( f"Nooooooooo! {ex}" )
                            sys.exit(1)
                    board.output_grid()
                    continue
                else:
                    output( "   use --force to switch to brute force methods" )
                break
            
    except Exception as ex:
        output( "* Fatal Error" )
        output( traceback.format_exc() )
        board.output_grid()
