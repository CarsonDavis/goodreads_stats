ok. so first i started doing some architecture research, and realized that i had too many unknowns
- how long will api queries take? Am I going to be able to do this on a lambda?
- what does my export even look like? what fields can I count on?

so, the next step is to do the data_analysis.md, which was in claude code.
it generated anaylsis_results.md. at this point, i start talking on claude to make a plan for actually testing out the api

ok, so now we write some initial tests, but we aren't getting the results we expected out of the api
https://claude.ai/chat/a91d9494-4381-4b05-a9ee-c2567b01d241
turns out that it was getting the basic fields but NOT everything we wanted
after "are we sure that we are using google books the correct way? lets get some links to the documentation", we can then get a better testing script
lesson: do this type of prompting from the start.

ok, now we can see in the browser that the file has surpassed 800 lines and is getting unwieldy. lets refactor it in claude code to be easier to work with

python -m api.single_book_tester "fork"

now we have a pretty nice little testing setup, and start digging deep