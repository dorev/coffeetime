using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerState : MonoBehaviour
{
    public CoffeeBar coffeeBar;
    public int maxCoffee = 100;
    public int currentCoffee;

    void Start()
    {
        coffeeBar.SetMaxCoffee(maxCoffee);
        currentCoffee = maxCoffee;
    }

    // Update is called once per frame
    void Update()
    {
        if(Input.GetKeyDown(KeyCode.Space))
        {
            DrinkCoffee(10);
        }
    }

    public void DrinkCoffee(int coffeeAmount)
    {
        if((currentCoffee - coffeeAmount) < 0)
        {
            currentCoffee = 0;
        }
        else
        {
            currentCoffee -= coffeeAmount;
        }
        coffeeBar.SetCoffee(currentCoffee);
        Debug.Log("Gulp! Drinks " + coffeeAmount + " coffee. Current coffee level is " + currentCoffee);
    }
    public void RefillCoffee(int coffeeAmount)
    {
        if((currentCoffee + coffeeAmount) > maxCoffee)
        {
            currentCoffee = maxCoffee;
        }
        else
        {
            currentCoffee += coffeeAmount;
        }
        coffeeBar.SetCoffee(currentCoffee);
        Debug.Log("Fuck yeah!! Refills " + coffeeAmount + " coffee. Current coffee level is " + currentCoffee);
    }
}
