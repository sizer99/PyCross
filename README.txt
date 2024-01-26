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


