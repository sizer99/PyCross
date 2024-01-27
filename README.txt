PyCross

Copyright 2024 Ron Dippold

-= Overview =-

  This is a simple little python Picross / Nanogram solver.  I wrote it because
  I got mad at Pictopix for giving me a puzzle that I was sure didn't have
  enough information to solve.  So I wrote this solver and the solver was
  able to solve the puzzle, so I was wrong.  ^_^

  However, later I did actually come across some puzzles where the completely
  deterministic solver was unable to solve the puzzle (Cash Register) so I
  added the --force option which looks for a row/col with few moves and picks
  one of the moves and runs with it.  If that causes a contradiction it moves
  back to before it did that (there's a stack). With this it's able to solve
  everything I've hit it with so far.

  This has some heuristics to speed things up - it can solve a very cantankerous
  brute force 30x3- picross in less than a second on a 4 year old CPU in --quiet
  mode. Most of the time spent is just printing the output.


-= Requirements =-

Python 3 - probably 3.9+ will work.  Tested on 3.11 and 3.12.

Python modules needed: colorama and numpy
    'pip install colorama numpy'     or 
    'apt install python-colorama python-numpy'


-= Input File Format =-

Do a 'pycross.py -H' (uppercase H) or look at any of the .solv files to see
the file format.  The 'Done' at the end is to make sure you entered the
correct number of column line info.


-= Usage =-

I usually run with this:
   pycross.py -vvvvv input.nano -o input.solv --force
   
which will brute force everything, show maximum debug, and output the
log to input.solv.

However if you're willing to gamble it will just work:
   pycross.py -q input.nano
is all it takes with the minimum output.

You can see the effects of --force by doing:
   pycross.py cash_register.nono
which will fail with
   Unsolved, but couldn't find anything else to do.
If you then use
   pycross.py cash_register.nono --force
you'll get the answer!


-= Releases =-
2024 Jan 25 1.00
	Initial Release
2024 Jan 26 1.01
	When doing --force, we could force a move that was illegal for the rows/cols the slice crossed,
	and since we had nothing checking legality overall, this would leave the board in an illegal
	state but 'done'.  Now we check when forcing a move, and check board legality after every step.
	Slows things down, but it's plenty fast anyhow.
	



--------

So after doing this I think it's kind of interesting to compare the algorithms this uses to the algorithms we use.

My algorithms when I'm just a meatsack doing a puzzle (I say left and right here for rows, sub top and bottom for columns):

-    If the hints are zero, everything's blank, obviously

-    If the total hint space ( 1 2 3 = 8 spaces) adds up to the unsolved space between the left and right blanks then just fill it in. The simplest form of this is where you have 20x20 and the hint is 20. But 15 4 is also full. Or if the right two columns are blank, then 14 3 fills the row.

-    If you have a filled space near a left or right edge, then you can extend filled spaces that far beyond it. For instance, if you have 5 2 3 as the hints, and you have a filled space in the third column, then you can fill in the 4th and 5th columns, because they must be filled.

-    Similarly if your hints are 5 3 4 and you have the 5 filled, then there's an unknown and a blank and a fill, then that fill must be the start of the 3. Or if you have 5 5 5 and the first 5 is completed, then you have unknown, unknown, filled, then the next two cells must be filled.

On the other hand, when I'm doing the it programatically, my only logic is:

-    If the hints are zero, everything's blank. (this is a speedup, could be skipped)

-    If the hints fill the unsolved space, then put them in, we're done. (this is a speedup, could be skipped)

-    If there's no possibility of a hint producing a filled cell, shortcut. For instance, in a 10 wide grid, take 1 2 as hints. The total width is 3 + 1 = 4, 10 - 2 = 8, there's no possibility there's anything useful from trying this line, so just skip it. On the other hand if you have 1 2 3 as hints, then the total width is 6 + 2 = 8. 10 - 8 = 2. There's going to be a fixed cell for 3, so evaluate it. (this is a speedup, could be skipped)

-    Otherwise, try every single combination of positions for the hints. If they fail (like trying to put a filled space over a blank space) then fail and do the next combo. Keep count of the number of filled spaces for each cell.

	- Once done with every single combo, if the number of filled spaces in a cell is zero then this must be a blank cell.

	- Similarly, if the number of filled spaces in a cell is equal to the number of legit positions, then this space must be filled.

    - This is the only step that is strictly necessary. All the others are just speedups.
	