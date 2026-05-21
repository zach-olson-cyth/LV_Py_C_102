CC ?= x86_64-linux-gnu-gcc
HOSTCC ?= gcc
CFLAGS := -O2 -fPIC -Wall -Wextra -std=c99 -D_GNU_SOURCE
LDFLAGS := -shared -lm
SRC := tank3_lvrt.c
SO := tank3_lvrt.so
TEST := tank3_lvrt_test

.PHONY: all test clean symbols

all: $(SO)

$(SO): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

test: $(TEST)
	./$(TEST)

$(TEST): $(SRC)
	$(HOSTCC) -O2 -Wall -Wextra -std=c99 -DTANK3_SMOKE_TEST -o $@ $< -lm

symbols: $(SO)
	nm -D $(SO) | grep " T " || true

clean:
	rm -f $(SO) $(TEST)
